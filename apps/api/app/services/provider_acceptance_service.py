from __future__ import annotations

from dataclasses import dataclass

from app.domain.order_lifecycle import (
    OrderStatus,
    OrderStatusTransitionError,
    OrderTransitionTrigger,
    transition_order_status,
)
from app.domain.provider_adapter import (
    AcceptanceDecision,
    AcceptanceResult,
    ProviderAdapter,
    ProviderOrderState,
)
from app.models.order import Order
from app.repositories.order_repository import OrderRepository

CUSTOMER_SAFE_REJECTION_REASON_BY_CODE = {
    "provider_rejected": "provider_unable_to_fulfill",
    "not_accepted": "provider_unable_to_fulfill",
    "provider_timeout": "provider_unable_to_fulfill",
    "capacity_unavailable": "provider_capacity_unavailable",
    "unsupported_configuration": "provider_unable_to_fulfill",
}
"""Customer-safe rejection reasons keyed by provider/internal reason codes."""


class ProviderAcceptanceRejected(ValueError):
    """Raised when provider acceptance/rejection processing is rejected.

    Attributes:
        code: Stable machine-readable rejection reason for routes and tests.
        message: Safe human-readable rejection message.
    """

    def __init__(self, code: str, message: str) -> None:
        """Store a stable rejection code and safe message.

        Args:
            code: Stable machine-readable rejection reason.
            message: Safe human-readable rejection message.

        Side effects:
            None.
        """
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProviderAcceptanceProcessingResult:
    """Result of processing one provider acceptance/rejection decision.

    Attributes:
        order: Current persisted Order after processing.
        decision: Provider decision that was requested.
        idempotent: Whether the persisted state already represented the same
            provider decision.
        customer_safe_status: Customer-safe status mapped from the adapter
            response or existing persisted order state.
        customer_safe_reason_code: Customer-safe rejection reason, when the
            provider rejected the order.
    """

    order: Order
    decision: AcceptanceDecision
    idempotent: bool
    customer_safe_status: ProviderOrderState
    customer_safe_reason_code: str | None = None


class ProviderAcceptanceService:
    """Persist provider acceptance/rejection decisions after paid-order handoff.

    The service consumes backend-owned provider adapter responses for orders
    already sent to a provider. It does not trust frontend/customer status or
    reason claims, does not mutate payment verification fields, and validates
    every persisted status change through the order lifecycle boundary.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        provider_adapter: ProviderAdapter,
    ) -> None:
        """Store repository and adapter dependencies.

        Args:
            order_repository: Repository used to load and persist orders.
            provider_adapter: Provider adapter boundary used to record the
                provider decision.

        Side effects:
            None.
        """
        self.order_repository = order_repository
        self.provider_adapter = provider_adapter

    def process_provider_decision(
        self,
        order_id: int,
        decision: AcceptanceDecision,
    ) -> ProviderAcceptanceProcessingResult:
        """Record and persist one provider acceptance/rejection decision.

        Args:
            order_id: Persisted order identifier.
            decision: Backend-owned provider decision to record through the
                adapter boundary.

        Returns:
            Processing result containing the current persisted order and
            customer-safe status/reason data.

        Side effects:
            For eligible `sent_to_provider` orders, calls the provider adapter
            and persists the resulting lifecycle status. Idempotent replays and
            rejected decisions do not mutate the order or payment fields.

        Raises:
            ProviderAcceptanceRejected: If the order is missing, current state
                is invalid, adapter response is unsafe/inconsistent, or the
                decision conflicts with a previously persisted outcome.
        """
        order = self.order_repository.get_order_by_id(order_id)
        if order is None:
            raise ProviderAcceptanceRejected(
                code="order_not_found",
                message="Order was not found.",
            )

        order_status = self._order_status(order)
        idempotent_result = self._idempotent_result(order, order_status, decision)
        if idempotent_result is not None:
            return idempotent_result

        self._reject_conflicting_decision(order_status, decision)
        self._validate_processable_order(order, order_status)

        provider_result = self.provider_adapter.record_acceptance(
            order.provider_handoff_reference,
            decision,
        )
        self._validate_provider_reference(
            provider_result,
            order.provider_handoff_reference,
        )
        target_status = self._validated_target_status(provider_result, decision)
        trigger = (
            OrderTransitionTrigger.PROVIDER_ACCEPTED
            if target_status is OrderStatus.ACCEPTED
            else OrderTransitionTrigger.PROVIDER_REJECTED
        )

        try:
            transition_order_status(order_status, target_status, trigger)
        except OrderStatusTransitionError as exc:
            raise ProviderAcceptanceRejected(
                code="invalid_order_transition",
                message="Provider decision is not allowed for this order state.",
            ) from exc

        updated_order = self.order_repository.record_provider_acceptance_outcome(
            order,
            status=target_status,
        )
        return ProviderAcceptanceProcessingResult(
            order=updated_order,
            decision=decision,
            idempotent=False,
            customer_safe_status=self._customer_safe_status(target_status),
            customer_safe_reason_code=(
                self._customer_safe_rejection_reason(provider_result.reason_code)
                if target_status is OrderStatus.CANCELLED
                else None
            ),
        )

    @staticmethod
    def _order_status(order: Order) -> OrderStatus:
        """Return the canonical order status or reject unsupported values."""
        try:
            return OrderStatus(order.status)
        except ValueError as exc:
            raise ProviderAcceptanceRejected(
                code="invalid_order_status",
                message="Order has an unsupported status.",
            ) from exc

    def _idempotent_result(
        self,
        order: Order,
        order_status: OrderStatus,
        decision: AcceptanceDecision,
    ) -> ProviderAcceptanceProcessingResult | None:
        """Return an idempotent result when state already matches decision."""
        if (
            order_status is OrderStatus.ACCEPTED
            and decision is AcceptanceDecision.ACCEPT
        ):
            return ProviderAcceptanceProcessingResult(
                order=order,
                decision=decision,
                idempotent=True,
                customer_safe_status=ProviderOrderState.ACCEPTED,
            )

        if (
            order_status is OrderStatus.CANCELLED
            and decision is AcceptanceDecision.REJECT
            and order.provider_handoff_reference is not None
        ):
            return ProviderAcceptanceProcessingResult(
                order=order,
                decision=decision,
                idempotent=True,
                customer_safe_status=ProviderOrderState.REJECTED,
                customer_safe_reason_code=self._customer_safe_rejection_reason(
                    "provider_rejected",
                ),
            )

        return None

    @staticmethod
    def _reject_conflicting_decision(
        order_status: OrderStatus,
        decision: AcceptanceDecision,
    ) -> None:
        """Reject decisions that conflict with an already persisted outcome."""
        if (
            order_status is OrderStatus.ACCEPTED
            and decision is AcceptanceDecision.REJECT
        ) or (
            order_status is OrderStatus.CANCELLED
            and decision is AcceptanceDecision.ACCEPT
        ):
            raise ProviderAcceptanceRejected(
                code="provider_decision_conflict",
                message="Provider decision conflicts with the current order state.",
            )

    @staticmethod
    def _validate_processable_order(
        order: Order,
        order_status: OrderStatus,
    ) -> None:
        """Reject orders that must not call the provider acceptance boundary."""
        if order_status is not OrderStatus.SENT_TO_PROVIDER:
            raise ProviderAcceptanceRejected(
                code="order_not_sent_to_provider",
                message="Provider decision requires an order sent to provider.",
            )

        if (
            order.provider_handoff_reference is None
            or not order.provider_handoff_reference.strip()
        ):
            raise ProviderAcceptanceRejected(
                code="provider_handoff_reference_required",
                message="Provider decision requires a provider handoff reference.",
            )

    def _validated_target_status(
        self,
        provider_result: AcceptanceResult,
        decision: AcceptanceDecision,
    ) -> OrderStatus:
        """Validate adapter result consistency and return the target status."""
        if not provider_result.provider_reference.strip():
            raise ProviderAcceptanceRejected(
                code="provider_reference_required",
                message="Provider decision response requires a provider reference.",
            )

        if decision is AcceptanceDecision.ACCEPT:
            if (
                not provider_result.accepted
                or provider_result.customer_safe_status
                is not ProviderOrderState.ACCEPTED
            ):
                raise ProviderAcceptanceRejected(
                    code="provider_acceptance_result_mismatch",
                    message="Provider acceptance response did not map to accepted.",
                )
            return OrderStatus.ACCEPTED

        if (
            provider_result.accepted
            or provider_result.customer_safe_status is not ProviderOrderState.REJECTED
        ):
            raise ProviderAcceptanceRejected(
                code="provider_rejection_result_mismatch",
                message="Provider rejection response did not map to rejected.",
            )
        return OrderStatus.CANCELLED

    @staticmethod
    def _validate_provider_reference(
        provider_result: AcceptanceResult,
        expected_provider_reference: str,
    ) -> None:
        """Reject adapter results that reference a different provider order."""
        if provider_result.provider_reference != expected_provider_reference:
            raise ProviderAcceptanceRejected(
                code="provider_reference_mismatch",
                message="Provider decision response did not match this order.",
            )

    @staticmethod
    def _customer_safe_status(order_status: OrderStatus) -> ProviderOrderState:
        """Map persisted order status to a customer-safe provider status."""
        if order_status is OrderStatus.ACCEPTED:
            return ProviderOrderState.ACCEPTED
        return ProviderOrderState.REJECTED

    @staticmethod
    def _customer_safe_rejection_reason(reason_code: str | None) -> str:
        """Map provider/internal rejection reasons to customer-safe codes."""
        return CUSTOMER_SAFE_REJECTION_REASON_BY_CODE.get(
            reason_code or "provider_rejected",
            "provider_unable_to_fulfill",
        )
