from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OrderStatus(StrEnum):
    """Canonical Path A order statuses used for customer order tracking."""

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    SENT_TO_PROVIDER = "sent_to_provider"
    ACCEPTED = "accepted"
    IN_PRODUCTION = "in_production"
    READY_FOR_PICKUP = "ready_for_pickup"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLATION_REQUESTED = "cancellation_requested"
    CANCELLED = "cancelled"


class OrderTransitionTrigger(StrEnum):
    """Backend-owned events allowed to move an order between statuses."""

    VERIFIED_PAYMENT = "verified_payment"
    PROVIDER_HANDOFF_SENT = "provider_handoff_sent"
    PROVIDER_ACCEPTED = "provider_accepted"
    PROVIDER_REJECTED = "provider_rejected"
    PRODUCTION_STARTED = "production_started"
    PACKAGE_READY_FOR_PICKUP = "package_ready_for_pickup"
    CARRIER_QR_PICKUP_SCAN = "carrier_qr_pickup_scan"
    AUTHORIZED_OPERATOR_SHIPMENT_FALLBACK = "authorized_operator_shipment_fallback"
    DELIVERY_CONFIRMED = "delivery_confirmed"
    PRE_PAYMENT_CANCEL = "pre_payment_cancel"
    CUSTOMER_CANCELLATION_REQUESTED = "customer_cancellation_requested"
    CANCELLATION_APPROVED = "cancellation_approved"
    CANCELLATION_REJECTED = "cancellation_rejected"


class OrderStatusTransitionError(ValueError):
    """Raised when a requested order status transition is not allowed."""


@dataclass(frozen=True)
class OrderStatusTransition:
    """Validated order status transition result.

    Attributes:
        from_status: Status before the transition.
        to_status: Status after the transition.
        trigger: Backend-owned event that justified the transition.
    """

    from_status: OrderStatus
    to_status: OrderStatus
    trigger: OrderTransitionTrigger


TERMINAL_ORDER_STATUSES = frozenset(
    {
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
    }
)
"""Statuses that do not allow further lifecycle transitions."""


CANCELLATION_REQUESTABLE_STATUSES = frozenset(
    {
        OrderStatus.CONFIRMED,
        OrderStatus.ACCEPTED,
        OrderStatus.IN_PRODUCTION,
    }
)
"""Paid statuses from which a customer may request cancellation."""


ORDER_STATUS_TRANSITIONS: dict[
    tuple[OrderStatus, OrderStatus],
    frozenset[OrderTransitionTrigger],
] = {
    (OrderStatus.DRAFT, OrderStatus.CONFIRMED): frozenset(
        {OrderTransitionTrigger.VERIFIED_PAYMENT}
    ),
    (OrderStatus.CONFIRMED, OrderStatus.SENT_TO_PROVIDER): frozenset(
        {OrderTransitionTrigger.PROVIDER_HANDOFF_SENT}
    ),
    (OrderStatus.SENT_TO_PROVIDER, OrderStatus.ACCEPTED): frozenset(
        {OrderTransitionTrigger.PROVIDER_ACCEPTED}
    ),
    (OrderStatus.SENT_TO_PROVIDER, OrderStatus.CANCELLED): frozenset(
        {OrderTransitionTrigger.PROVIDER_REJECTED}
    ),
    (OrderStatus.ACCEPTED, OrderStatus.IN_PRODUCTION): frozenset(
        {OrderTransitionTrigger.PRODUCTION_STARTED}
    ),
    (OrderStatus.IN_PRODUCTION, OrderStatus.READY_FOR_PICKUP): frozenset(
        {OrderTransitionTrigger.PACKAGE_READY_FOR_PICKUP}
    ),
    (OrderStatus.READY_FOR_PICKUP, OrderStatus.SHIPPED): frozenset(
        {
            OrderTransitionTrigger.CARRIER_QR_PICKUP_SCAN,
            OrderTransitionTrigger.AUTHORIZED_OPERATOR_SHIPMENT_FALLBACK,
        }
    ),
    (OrderStatus.SHIPPED, OrderStatus.DELIVERED): frozenset(
        {OrderTransitionTrigger.DELIVERY_CONFIRMED}
    ),
    (OrderStatus.DRAFT, OrderStatus.CANCELLED): frozenset(
        {OrderTransitionTrigger.PRE_PAYMENT_CANCEL}
    ),
    (OrderStatus.CONFIRMED, OrderStatus.CANCELLATION_REQUESTED): frozenset(
        {OrderTransitionTrigger.CUSTOMER_CANCELLATION_REQUESTED}
    ),
    (OrderStatus.ACCEPTED, OrderStatus.CANCELLATION_REQUESTED): frozenset(
        {OrderTransitionTrigger.CUSTOMER_CANCELLATION_REQUESTED}
    ),
    (OrderStatus.IN_PRODUCTION, OrderStatus.CANCELLATION_REQUESTED): frozenset(
        {OrderTransitionTrigger.CUSTOMER_CANCELLATION_REQUESTED}
    ),
    (OrderStatus.CANCELLATION_REQUESTED, OrderStatus.CANCELLED): frozenset(
        {OrderTransitionTrigger.CANCELLATION_APPROVED}
    ),
    (OrderStatus.CANCELLATION_REQUESTED, OrderStatus.CONFIRMED): frozenset(
        {OrderTransitionTrigger.CANCELLATION_REJECTED}
    ),
    (OrderStatus.CANCELLATION_REQUESTED, OrderStatus.ACCEPTED): frozenset(
        {OrderTransitionTrigger.CANCELLATION_REJECTED}
    ),
    (OrderStatus.CANCELLATION_REQUESTED, OrderStatus.IN_PRODUCTION): frozenset(
        {OrderTransitionTrigger.CANCELLATION_REJECTED}
    ),
}
"""Allowed Path A lifecycle transitions keyed by source and destination status."""


def transition_order_status(
    current_status: OrderStatus,
    target_status: OrderStatus,
    trigger: OrderTransitionTrigger,
    *,
    cancellation_requested_from: OrderStatus | None = None,
) -> OrderStatusTransition:
    """Validate and describe a Path A order status transition.

    Args:
        current_status: Current persisted order status.
        target_status: Requested next order status.
        trigger: Backend-owned event authorizing the transition.
        cancellation_requested_from: Previous paid status used when rejecting a
            cancellation request.

    Returns:
        A validated immutable transition description.

    Raises:
        OrderStatusTransitionError: If the status pair, trigger, terminal
            source, or cancellation rejection target is invalid.

    Side effects:
        None. Callers must persist the returned target only after validation.
    """
    if current_status in TERMINAL_ORDER_STATUSES:
        raise OrderStatusTransitionError(
            f"Cannot transition terminal order status '{current_status}'."
        )

    allowed_triggers = ORDER_STATUS_TRANSITIONS.get((current_status, target_status))
    if allowed_triggers is None or trigger not in allowed_triggers:
        raise OrderStatusTransitionError(
            "Invalid order transition "
            f"'{current_status}' -> '{target_status}' for trigger '{trigger}'."
        )

    if trigger is OrderTransitionTrigger.CANCELLATION_REJECTED:
        _validate_cancellation_rejection_target(
            target_status,
            cancellation_requested_from,
        )

    return OrderStatusTransition(
        from_status=current_status,
        to_status=target_status,
        trigger=trigger,
    )


def _validate_cancellation_rejection_target(
    target_status: OrderStatus,
    cancellation_requested_from: OrderStatus | None,
) -> None:
    """Ensure rejected cancellation requests return to their prior paid state."""
    if cancellation_requested_from not in CANCELLATION_REQUESTABLE_STATUSES:
        raise OrderStatusTransitionError(
            "Cancellation rejection requires the original paid order status."
        )

    if target_status is not cancellation_requested_from:
        raise OrderStatusTransitionError(
            "Cancellation rejection must return to the status from which the "
            "request was made."
        )
