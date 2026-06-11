from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.order_lifecycle import (
    OrderStatus,
    OrderTransitionTrigger,
    transition_order_status,
)
from app.domain.payment_lifecycle import (
    PaymentLifecycleError,
    PaymentStatus,
    validate_provider_handoff_eligibility,
)
from app.domain.provider_adapter import HandoffResult, HandoffState, ProviderAdapter
from app.models.order import Order
from app.models.order_item import OrderItem
from app.repositories.order_repository import OrderRepository
from app.services.provider_handoff_payload_service import (
    ProviderHandoffPayloadRejected,
    ProviderHandoffPayloadService,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderHandoffTransmissionResult:
    """Successful paid-order provider handoff transmission result.

    Attributes:
        order: Persisted Order after handoff success fields were recorded.
        provider_reference: Provider-side handoff reference returned by the
            adapter.
        idempotency_key: Stable retry key used for this order/provider handoff.
        sent_at: Backend timestamp recorded for the successful transmission.
    """

    order: Order
    provider_reference: str
    idempotency_key: str
    sent_at: datetime


@dataclass(frozen=True)
class ProviderHandoffTransmissionRejected(ValueError):
    """Raised when paid-order provider handoff transmission is rejected.

    Attributes:
        code: Stable rejection reason for callers and tests.
        message: Human-readable explanation of the rejection.
        reason_code: Optional provider or validation reason code.
    """

    code: str
    message: str
    reason_code: str | None = None

    def __str__(self) -> str:
        """Return the human-readable rejection message."""
        return self.message


class ProviderHandoffTransmissionService:
    """Send verified paid orders through the provider adapter boundary.

    The service is the #61 transmission coordinator. It validates handoff
    eligibility before payload generation, prepares the #35 payload immediately
    before adapter transmission, and persists only the minimum successful
    transmission result needed for traceability. It does not verify payments,
    confirm orders, persist provider acceptance/rejection, or expose sensitive
    payment/customer fields in logs.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        payload_service: ProviderHandoffPayloadService,
        provider_adapter: ProviderAdapter,
    ) -> None:
        """Store provider handoff transmission dependencies.

        Args:
            order_repository: Repository used to persist successful handoff
                transmission fields.
            payload_service: Service that builds provider-neutral handoff
                requests from persisted backend snapshots.
            provider_adapter: Adapter boundary used to transmit the paid order.
        """
        self.order_repository = order_repository
        self.payload_service = payload_service
        self.provider_adapter = provider_adapter

    def transmit_paid_order(
        self,
        order: Order,
        payment_status: PaymentStatus,
    ) -> ProviderHandoffTransmissionResult:
        """Transmit one verified paid order to its assigned provider.

        Args:
            order: Persisted Order with item snapshots loaded.
            payment_status: Backend-owned payment status from the trusted
                payment confirmation path.

        Returns:
            Successful provider handoff transmission result with the updated
            Order and provider reference.

        Raises:
            ProviderHandoffTransmissionRejected: If payment, order, provider
                assignment, payload preparation, adapter transmission, or
                status transition validation rejects the handoff.

        Side effects:
            Calls the provider adapter only after validation and payload
            preparation succeed. On successful adapter transmission, updates
            the Order status to `sent_to_provider` and records the provider
            handoff reference and sent timestamp. Failed transmission does not
            write provider handoff success fields.
        """
        self._validate_transmission_eligibility(order, payment_status)

        request = self._prepare_handoff_request(order, payment_status)
        handoff_result = self.provider_adapter.handoff_paid_order(request)

        if handoff_result.state is not HandoffState.SENT:
            self._log_handoff_failure(order, handoff_result)
            raise ProviderHandoffTransmissionRejected(
                code="provider_handoff_failed",
                message="Provider handoff transmission failed.",
                reason_code=handoff_result.reason_code or handoff_result.state.value,
            )

        self._validate_order_transition(order)
        provider_reference = self._provider_reference(handoff_result)
        sent_at = datetime.now(UTC)
        updated_order = self.order_repository.record_provider_handoff_sent(
            order,
            provider_reference=provider_reference,
            sent_at=sent_at,
        )
        self._log_handoff_success(updated_order, handoff_result)

        return ProviderHandoffTransmissionResult(
            order=updated_order,
            provider_reference=provider_reference,
            idempotency_key=handoff_result.idempotency_key,
            sent_at=sent_at,
        )

    def _validate_transmission_eligibility(
        self,
        order: Order,
        payment_status: PaymentStatus,
    ) -> None:
        """Validate handoff eligibility before payload generation."""
        order_status = self._order_status(order)
        try:
            validate_provider_handoff_eligibility(payment_status, order_status)
        except PaymentLifecycleError as exc:
            raise ProviderHandoffTransmissionRejected(
                code=self._eligibility_code(payment_status, order_status),
                message=str(exc),
            ) from exc

        if order.payment_verified_at is None:
            raise ProviderHandoffTransmissionRejected(
                code="payment_verification_timestamp_required",
                message=(
                    "Provider handoff transmission requires persisted payment "
                    "verification timestamp."
                ),
            )

        self._validate_provider_assignment(order)

    def _prepare_handoff_request(self, order: Order, payment_status: PaymentStatus):
        """Prepare the provider payload immediately before adapter handoff."""
        try:
            return self.payload_service.prepare_handoff_request(order, payment_status)
        except ProviderHandoffPayloadRejected as exc:
            raise ProviderHandoffTransmissionRejected(
                code=exc.code,
                message=exc.message,
            ) from exc

    def _validate_order_transition(self, order: Order) -> None:
        """Validate successful handoff may move the order to sent_to_provider."""
        try:
            transition_order_status(
                self._order_status(order),
                OrderStatus.SENT_TO_PROVIDER,
                OrderTransitionTrigger.PROVIDER_HANDOFF_SENT,
            )
        except ValueError as exc:
            raise ProviderHandoffTransmissionRejected(
                code="order_transition_rejected",
                message="Provider handoff cannot update order status.",
            ) from exc

    def _validate_provider_assignment(self, order: Order) -> None:
        """Reject orders without a backend-owned provider assignment."""
        if order.assigned_provider_id and order.assigned_provider_id.strip():
            return

        item_provider_ids = {
            item.assigned_provider_id.strip()
            for item in self._items(order)
            if item.assigned_provider_id and item.assigned_provider_id.strip()
        }
        if len(item_provider_ids) == 1:
            return

        raise ProviderHandoffTransmissionRejected(
            code="provider_assignment_required",
            message="Provider handoff transmission requires provider assignment.",
        )

    @staticmethod
    def _items(order: Order) -> list[OrderItem]:
        """Return currently loaded order items as a list."""
        return list(getattr(order, "items", []) or [])

    @staticmethod
    def _order_status(order: Order) -> OrderStatus:
        """Return the canonical order status or reject unsupported values."""
        try:
            return OrderStatus(order.status)
        except ValueError as exc:
            raise ProviderHandoffTransmissionRejected(
                code="invalid_order_status",
                message="Provider handoff requires a supported order status.",
            ) from exc

    @staticmethod
    def _eligibility_code(
        payment_status: PaymentStatus,
        order_status: OrderStatus,
    ) -> str:
        """Return a stable eligibility rejection code."""
        if payment_status is not PaymentStatus.VERIFIED:
            return "payment_not_verified"
        if order_status is not OrderStatus.CONFIRMED:
            return "order_not_confirmed"
        return "provider_handoff_not_eligible"

    @staticmethod
    def _provider_reference(handoff_result: HandoffResult) -> str:
        """Return a non-empty provider reference from a successful handoff."""
        provider_reference = handoff_result.provider_reference.strip()
        if not provider_reference:
            raise ProviderHandoffTransmissionRejected(
                code="provider_reference_required",
                message="Provider handoff success requires a provider reference.",
            )
        return provider_reference

    @staticmethod
    def _log_handoff_success(
        order: Order,
        handoff_result: HandoffResult,
    ) -> None:
        """Log successful handoff metadata without sensitive payment details."""
        logger.info(
            "provider_handoff_sent order_id=%s assigned_provider_id=%s "
            "idempotency_key=%s provider_reference=%s",
            order.id,
            order.assigned_provider_id,
            handoff_result.idempotency_key,
            handoff_result.provider_reference,
        )

    @staticmethod
    def _log_handoff_failure(
        order: Order,
        handoff_result: HandoffResult,
    ) -> None:
        """Log failed handoff metadata without sensitive payment details."""
        logger.warning(
            "provider_handoff_failed order_id=%s assigned_provider_id=%s "
            "idempotency_key=%s handoff_state=%s reason_code=%s",
            order.id,
            order.assigned_provider_id,
            handoff_result.idempotency_key,
            handoff_result.state.value,
            handoff_result.reason_code,
        )
