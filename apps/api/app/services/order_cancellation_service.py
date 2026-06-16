from __future__ import annotations

from dataclasses import dataclass

from app.domain.order_lifecycle import (
    OrderStatus,
    OrderStatusTransitionError,
    OrderTransitionTrigger,
    transition_order_status,
)
from app.models.order import Order
from app.repositories.order_repository import OrderRepository

CUSTOMER_CANCELLATION_REQUEST_AUDIT_ACTION = "order.cancellation.request"
ADMIN_CANCELLATION_APPROVAL_AUDIT_ACTION = "order.cancellation.approve"
ADMIN_CANCELLATION_REJECTION_AUDIT_ACTION = "order.cancellation.reject"


class OrderCancellationRejected(ValueError):
    """Raised when order cancellation workflow processing is rejected.

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
class OrderCancellationResult:
    """Result of processing one cancellation request or admin resolution.

    Attributes:
        order: Current Order after processing.
        from_status: Order status before the accepted transition.
        target_status: Order status written by the workflow.
        trigger: Lifecycle trigger used to validate the transition.
        cancellation_requested_from: Prior paid status retained for customer
            requests or used to restore rejected requests.
    """

    order: Order
    from_status: OrderStatus
    target_status: OrderStatus
    trigger: OrderTransitionTrigger
    cancellation_requested_from: OrderStatus | None = None


class OrderCancellationService:
    """Process paid-order cancellation requests and admin resolutions.

    The service enforces ownership for customer requests, validates all status
    changes through the order lifecycle boundary, preserves payment/provider
    history fields, and persists only the order status plus
    `cancellation_requested_from` metadata needed to resolve a request later.
    """

    def __init__(self, order_repository: OrderRepository) -> None:
        """Store the repository dependency used by the workflow.

        Args:
            order_repository: Repository used to load and stage order updates.
        """
        self.order_repository = order_repository

    def request_cancellation(
        self,
        order_id: int,
        *,
        customer_id: int,
    ) -> OrderCancellationResult:
        """Request cancellation for one customer-owned paid order.

        Args:
            order_id: Persisted order identifier.
            customer_id: Backend-derived authenticated customer identifier.

        Returns:
            Processing result containing transition metadata and the staged
            order update.

        Side effects:
            For eligible orders, stages a transition to
            `cancellation_requested` and persists the prior paid status in
            `cancellation_requested_from`. Payment confirmation and provider
            fulfillment fields remain untouched. The caller remains responsible
            for committing or rolling back.

        Raises:
            OrderCancellationRejected: If the order is missing, not owned by
                the customer, or not in an eligible paid status.
        """
        order = self.order_repository.get_order_for_customer(order_id, customer_id)
        if order is None:
            raise OrderCancellationRejected(
                code="order_not_found",
                message="Order was not found.",
            )

        order_status = self._order_status(order)
        try:
            transition_order_status(
                order_status,
                OrderStatus.CANCELLATION_REQUESTED,
                OrderTransitionTrigger.CUSTOMER_CANCELLATION_REQUESTED,
            )
        except OrderStatusTransitionError as exc:
            raise OrderCancellationRejected(
                code="order_cancellation_not_allowed",
                message="Cancellation request is not allowed for this order state.",
            ) from exc

        updated_order = self.order_repository.record_customer_cancellation_request(
            order,
            from_status=order_status,
        )
        return OrderCancellationResult(
            order=updated_order,
            from_status=order_status,
            target_status=OrderStatus.CANCELLATION_REQUESTED,
            trigger=OrderTransitionTrigger.CUSTOMER_CANCELLATION_REQUESTED,
            cancellation_requested_from=order_status,
        )

    def approve_cancellation(self, order_id: int) -> OrderCancellationResult:
        """Approve one pending cancellation request.

        Args:
            order_id: Persisted order identifier.

        Returns:
            Processing result containing transition metadata and the staged
            order update.

        Side effects:
            For eligible orders, stages a transition from
            `cancellation_requested` to `cancelled` and clears
            `cancellation_requested_from`. Payment confirmation and provider
            fulfillment fields remain untouched. The caller remains responsible
            for committing or rolling back.

        Raises:
            OrderCancellationRejected: If the order is missing or not awaiting
                cancellation review.
        """
        order = self._pending_cancellation_order(order_id)
        original_status = self._cancellation_requested_from(order)

        try:
            transition_order_status(
                OrderStatus.CANCELLATION_REQUESTED,
                OrderStatus.CANCELLED,
                OrderTransitionTrigger.CANCELLATION_APPROVED,
            )
        except OrderStatusTransitionError as exc:
            raise OrderCancellationRejected(
                code="order_not_cancellation_requested",
                message="Cancellation approval requires a pending request.",
            ) from exc

        updated_order = self.order_repository.resolve_customer_cancellation_request(
            order,
            status=OrderStatus.CANCELLED,
        )
        return OrderCancellationResult(
            order=updated_order,
            from_status=OrderStatus.CANCELLATION_REQUESTED,
            target_status=OrderStatus.CANCELLED,
            trigger=OrderTransitionTrigger.CANCELLATION_APPROVED,
            cancellation_requested_from=original_status,
        )

    def reject_cancellation(self, order_id: int) -> OrderCancellationResult:
        """Reject one pending cancellation request and restore the prior status.

        Args:
            order_id: Persisted order identifier.

        Returns:
            Processing result containing transition metadata and the staged
            order update.

        Side effects:
            For eligible orders, stages a transition from
            `cancellation_requested` back to the original paid status and
            clears `cancellation_requested_from`. Payment confirmation and
            provider fulfillment fields remain untouched. The caller remains
            responsible for committing or rolling back.

        Raises:
            OrderCancellationRejected: If the order is missing, not awaiting
                cancellation review, or lacks a valid original paid status.
        """
        order = self._pending_cancellation_order(order_id)
        original_status = self._cancellation_requested_from(order)

        try:
            transition_order_status(
                OrderStatus.CANCELLATION_REQUESTED,
                original_status,
                OrderTransitionTrigger.CANCELLATION_REJECTED,
                cancellation_requested_from=original_status,
            )
        except OrderStatusTransitionError as exc:
            raise OrderCancellationRejected(
                code="invalid_cancellation_requested_from",
                message="Cancellation request is missing a valid original status.",
            ) from exc

        updated_order = self.order_repository.resolve_customer_cancellation_request(
            order,
            status=original_status,
        )
        return OrderCancellationResult(
            order=updated_order,
            from_status=OrderStatus.CANCELLATION_REQUESTED,
            target_status=original_status,
            trigger=OrderTransitionTrigger.CANCELLATION_REJECTED,
            cancellation_requested_from=original_status,
        )

    def _pending_cancellation_order(self, order_id: int) -> Order:
        """Return one order awaiting cancellation review or reject it."""
        order = self.order_repository.get_order_by_id(order_id)
        if order is None:
            raise OrderCancellationRejected(
                code="order_not_found",
                message="Order was not found.",
            )

        if self._order_status(order) is not OrderStatus.CANCELLATION_REQUESTED:
            raise OrderCancellationRejected(
                code="order_not_cancellation_requested",
                message="Cancellation resolution requires a pending request.",
            )

        return order

    @staticmethod
    def _order_status(order: Order) -> OrderStatus:
        """Return the canonical order status or reject unsupported values."""
        try:
            return OrderStatus(order.status)
        except ValueError as exc:
            raise OrderCancellationRejected(
                code="invalid_order_status",
                message="Order has an unsupported status.",
            ) from exc

    def _cancellation_requested_from(self, order: Order) -> OrderStatus:
        """Return the original paid status stored on a pending request."""
        try:
            return OrderStatus(order.cancellation_requested_from)
        except ValueError as exc:
            raise OrderCancellationRejected(
                code="invalid_cancellation_requested_from",
                message="Cancellation request is missing a valid original status.",
            ) from exc
