from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.order_lifecycle import OrderStatus


class PaymentStatus(StrEnum):
    """Canonical Path A payment statuses before provider handoff."""

    INITIATED = "initiated"
    PENDING = "pending"
    REQUIRES_ACTION = "requires_action"
    VERIFIED = "verified"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PaymentTransitionTrigger(StrEnum):
    """Backend-owned events allowed to move a payment between statuses."""

    PAYMENT_INITIALIZED = "payment_initialized"
    PROVIDER_PENDING = "provider_pending"
    PROVIDER_REQUIRES_ACTION = "provider_requires_action"
    VERIFIED_PROVIDER_CONFIRMATION = "verified_provider_confirmation"
    PROVIDER_FAILED = "provider_failed"
    PROVIDER_CANCELLED = "provider_cancelled"
    PROVIDER_EXPIRED = "provider_expired"


class PaymentEventSource(StrEnum):
    """Sources that may report payment-related events to the backend."""

    PAYMENT_PROVIDER_WEBHOOK = "payment_provider_webhook"
    PAYMENT_PROVIDER_RECONCILIATION = "payment_provider_reconciliation"
    FRONTEND_RETURN = "frontend_return"
    PROVIDER_ADAPTER = "provider_adapter"


class PaymentLifecycleError(ValueError):
    """Raised when a payment lifecycle decision is not allowed."""


@dataclass(frozen=True)
class PaymentStatusTransition:
    """Validated payment status transition result.

    Attributes:
        from_status: Payment status before the transition.
        to_status: Payment status after the transition.
        trigger: Backend-owned event that justified the transition.
    """

    from_status: PaymentStatus
    to_status: PaymentStatus
    trigger: PaymentTransitionTrigger


@dataclass(frozen=True)
class OrderConfirmationEligibility:
    """Validated result allowing payment confirmation to confirm an order.

    Attributes:
        payment_status: Verified payment status used for confirmation.
        order_status: Draft order status allowed to move to confirmed.
        event_source: Trusted payment-provider source of the confirmation.
    """

    payment_status: PaymentStatus
    order_status: OrderStatus
    event_source: PaymentEventSource


@dataclass(frozen=True)
class ProviderHandoffEligibility:
    """Validated result allowing a paid order to become handoff-eligible.

    Attributes:
        payment_status: Verified payment status.
        order_status: Confirmed order status.
    """

    payment_status: PaymentStatus
    order_status: OrderStatus


TERMINAL_PAYMENT_STATUSES = frozenset(
    {
        PaymentStatus.VERIFIED,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
        PaymentStatus.EXPIRED,
    }
)
"""Payment statuses that do not allow further lifecycle transitions."""


FAILED_PAYMENT_STATUSES = frozenset(
    {
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
        PaymentStatus.EXPIRED,
    }
)
"""Payment statuses that must never confirm orders or trigger handoff."""


PAYMENT_STATUS_TRANSITIONS: dict[
    tuple[PaymentStatus, PaymentStatus],
    frozenset[PaymentTransitionTrigger],
] = {
    (PaymentStatus.INITIATED, PaymentStatus.PENDING): frozenset(
        {PaymentTransitionTrigger.PROVIDER_PENDING}
    ),
    (PaymentStatus.INITIATED, PaymentStatus.REQUIRES_ACTION): frozenset(
        {PaymentTransitionTrigger.PROVIDER_REQUIRES_ACTION}
    ),
    (PaymentStatus.INITIATED, PaymentStatus.VERIFIED): frozenset(
        {PaymentTransitionTrigger.VERIFIED_PROVIDER_CONFIRMATION}
    ),
    (PaymentStatus.PENDING, PaymentStatus.REQUIRES_ACTION): frozenset(
        {PaymentTransitionTrigger.PROVIDER_REQUIRES_ACTION}
    ),
    (PaymentStatus.REQUIRES_ACTION, PaymentStatus.PENDING): frozenset(
        {PaymentTransitionTrigger.PROVIDER_PENDING}
    ),
    (PaymentStatus.PENDING, PaymentStatus.VERIFIED): frozenset(
        {PaymentTransitionTrigger.VERIFIED_PROVIDER_CONFIRMATION}
    ),
    (PaymentStatus.REQUIRES_ACTION, PaymentStatus.VERIFIED): frozenset(
        {PaymentTransitionTrigger.VERIFIED_PROVIDER_CONFIRMATION}
    ),
    (PaymentStatus.INITIATED, PaymentStatus.FAILED): frozenset(
        {PaymentTransitionTrigger.PROVIDER_FAILED}
    ),
    (PaymentStatus.PENDING, PaymentStatus.FAILED): frozenset(
        {PaymentTransitionTrigger.PROVIDER_FAILED}
    ),
    (PaymentStatus.REQUIRES_ACTION, PaymentStatus.FAILED): frozenset(
        {PaymentTransitionTrigger.PROVIDER_FAILED}
    ),
    (PaymentStatus.INITIATED, PaymentStatus.CANCELLED): frozenset(
        {PaymentTransitionTrigger.PROVIDER_CANCELLED}
    ),
    (PaymentStatus.PENDING, PaymentStatus.CANCELLED): frozenset(
        {PaymentTransitionTrigger.PROVIDER_CANCELLED}
    ),
    (PaymentStatus.REQUIRES_ACTION, PaymentStatus.CANCELLED): frozenset(
        {PaymentTransitionTrigger.PROVIDER_CANCELLED}
    ),
    (PaymentStatus.INITIATED, PaymentStatus.EXPIRED): frozenset(
        {PaymentTransitionTrigger.PROVIDER_EXPIRED}
    ),
    (PaymentStatus.PENDING, PaymentStatus.EXPIRED): frozenset(
        {PaymentTransitionTrigger.PROVIDER_EXPIRED}
    ),
    (PaymentStatus.REQUIRES_ACTION, PaymentStatus.EXPIRED): frozenset(
        {PaymentTransitionTrigger.PROVIDER_EXPIRED}
    ),
}
"""Allowed Path A payment transitions keyed by source and destination status."""


TRUSTED_PAYMENT_CONFIRMATION_SOURCES = frozenset(
    {
        PaymentEventSource.PAYMENT_PROVIDER_WEBHOOK,
        PaymentEventSource.PAYMENT_PROVIDER_RECONCILIATION,
    }
)
"""Payment event sources allowed to verify payment-provider confirmation."""


def transition_payment_status(
    current_status: PaymentStatus,
    target_status: PaymentStatus,
    trigger: PaymentTransitionTrigger,
    *,
    event_source: PaymentEventSource,
) -> PaymentStatusTransition:
    """Validate and describe a Path A payment status transition.

    Args:
        current_status: Current persisted payment status.
        target_status: Requested next payment status.
        trigger: Backend-owned event authorizing the transition.
        event_source: Source that reported or derived the payment event.

    Returns:
        A validated immutable transition description.

    Raises:
        PaymentLifecycleError: If the transition, trigger, event source, or
            terminal source state is invalid.

    Side effects:
        None. Callers must persist returned status changes only after
        validation succeeds.
    """
    if current_status in TERMINAL_PAYMENT_STATUSES:
        raise PaymentLifecycleError(
            f"Cannot transition terminal payment status '{current_status}'."
        )

    allowed_triggers = PAYMENT_STATUS_TRANSITIONS.get((current_status, target_status))
    if allowed_triggers is None or trigger not in allowed_triggers:
        raise PaymentLifecycleError(
            "Invalid payment transition "
            f"'{current_status}' -> '{target_status}' for trigger '{trigger}'."
        )

    if trigger is PaymentTransitionTrigger.VERIFIED_PROVIDER_CONFIRMATION:
        validate_payment_confirmation_source(event_source)

    return PaymentStatusTransition(
        from_status=current_status,
        to_status=target_status,
        trigger=trigger,
    )


def validate_payment_confirmation_source(
    event_source: PaymentEventSource,
) -> None:
    """Ensure only trusted payment-provider events can verify a payment.

    Args:
        event_source: Source that reported or derived the payment event.

    Raises:
        PaymentLifecycleError: If the source is frontend or provider-adapter
            supplied rather than payment-provider supplied.

    Side effects:
        None.
    """
    if event_source not in TRUSTED_PAYMENT_CONFIRMATION_SOURCES:
        raise PaymentLifecycleError(
            "Payment verification requires a trusted payment-provider event."
        )


def validate_order_confirmation_from_payment(
    payment_status: PaymentStatus,
    order_status: OrderStatus,
    *,
    event_source: PaymentEventSource,
) -> OrderConfirmationEligibility:
    """Validate that payment state can move a draft order to confirmed.

    Args:
        payment_status: Current payment status after lifecycle validation.
        order_status: Current order status before confirmation.
        event_source: Source that produced the payment confirmation.

    Returns:
        A validated immutable confirmation eligibility result.

    Raises:
        PaymentLifecycleError: If the payment is not verified, the source is
            not trusted, or the order is not still draft.

    Side effects:
        None.
    """
    validate_payment_confirmation_source(event_source)

    if payment_status is not PaymentStatus.VERIFIED:
        raise PaymentLifecycleError(
            "Order confirmation requires a verified payment status."
        )

    if order_status is not OrderStatus.DRAFT:
        raise PaymentLifecycleError(
            "Payment confirmation can only confirm draft orders."
        )

    return OrderConfirmationEligibility(
        payment_status=payment_status,
        order_status=order_status,
        event_source=event_source,
    )


def validate_provider_handoff_eligibility(
    payment_status: PaymentStatus,
    order_status: OrderStatus,
) -> ProviderHandoffEligibility:
    """Validate that an order is eligible for paid-order provider handoff.

    Args:
        payment_status: Current verified payment status.
        order_status: Current confirmed order status.

    Returns:
        A validated immutable provider handoff eligibility result.

    Raises:
        PaymentLifecycleError: If payment or order state is not handoff-ready.

    Side effects:
        None.
    """
    if payment_status is not PaymentStatus.VERIFIED:
        raise PaymentLifecycleError(
            "Provider handoff requires a verified payment status."
        )

    if order_status is not OrderStatus.CONFIRMED:
        raise PaymentLifecycleError(
            "Provider handoff requires a confirmed order status."
        )

    return ProviderHandoffEligibility(
        payment_status=payment_status,
        order_status=order_status,
    )
