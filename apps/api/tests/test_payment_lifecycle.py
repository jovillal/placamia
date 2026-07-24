from dataclasses import dataclass

import pytest
from app.domain.order_lifecycle import OrderStatus
from app.domain.payment_lifecycle import (
    FAILED_PAYMENT_STATUSES,
    PaymentEventSource,
    PaymentLifecycleError,
    PaymentStatus,
    PaymentTransitionTrigger,
    transition_payment_status,
    validate_order_confirmation_from_payment,
    validate_provider_handoff_eligibility,
)


@dataclass
class MutablePaymentRecord:
    """Tiny mutable stand-in proving domain validation has no side effects."""

    status: PaymentStatus


@dataclass
class MutableOrderRecord:
    """Tiny mutable stand-in proving order state is not changed on rejection."""

    status: OrderStatus


@pytest.mark.parametrize(
    ("current_status", "target_status", "trigger"),
    [
        (
            PaymentStatus.INITIATED,
            PaymentStatus.PENDING,
            PaymentTransitionTrigger.PROVIDER_PENDING,
        ),
        (
            PaymentStatus.INITIATED,
            PaymentStatus.REQUIRES_ACTION,
            PaymentTransitionTrigger.PROVIDER_REQUIRES_ACTION,
        ),
        (
            PaymentStatus.INITIATED,
            PaymentStatus.VERIFIED,
            PaymentTransitionTrigger.VERIFIED_PROVIDER_CONFIRMATION,
        ),
        (
            PaymentStatus.PENDING,
            PaymentStatus.VERIFIED,
            PaymentTransitionTrigger.VERIFIED_PROVIDER_CONFIRMATION,
        ),
        (
            PaymentStatus.REQUIRES_ACTION,
            PaymentStatus.VERIFIED,
            PaymentTransitionTrigger.VERIFIED_PROVIDER_CONFIRMATION,
        ),
        (
            PaymentStatus.PENDING,
            PaymentStatus.FAILED,
            PaymentTransitionTrigger.PROVIDER_FAILED,
        ),
        (
            PaymentStatus.PENDING,
            PaymentStatus.CANCELLED,
            PaymentTransitionTrigger.PROVIDER_CANCELLED,
        ),
        (
            PaymentStatus.PENDING,
            PaymentStatus.EXPIRED,
            PaymentTransitionTrigger.PROVIDER_EXPIRED,
        ),
    ],
)
def test_payment_status_transition_accepts_valid_provider_lifecycle_events(
    current_status,
    target_status,
    trigger,
):
    transition = transition_payment_status(
        current_status,
        target_status,
        trigger,
        event_source=PaymentEventSource.PAYMENT_PROVIDER_WEBHOOK,
    )

    assert transition.from_status is current_status
    assert transition.to_status is target_status
    assert transition.trigger is trigger


@pytest.mark.parametrize(
    "current_status",
    [PaymentStatus.INITIATED, PaymentStatus.REQUIRES_ACTION],
)
def test_checkout_window_elapsed_expires_only_restartable_payment(current_status):
    transition = transition_payment_status(
        current_status,
        PaymentStatus.EXPIRED,
        PaymentTransitionTrigger.CHECKOUT_WINDOW_ELAPSED,
        event_source=PaymentEventSource.PAYMENT_INITIALIZATION,
    )

    assert transition.to_status is PaymentStatus.EXPIRED


def test_checkout_window_elapsed_cannot_expire_pending_payment():
    with pytest.raises(PaymentLifecycleError):
        transition_payment_status(
            PaymentStatus.PENDING,
            PaymentStatus.EXPIRED,
            PaymentTransitionTrigger.CHECKOUT_WINDOW_ELAPSED,
            event_source=PaymentEventSource.PAYMENT_INITIALIZATION,
        )


@pytest.mark.parametrize(
    ("current_status", "target_status", "trigger"),
    [
        (
            PaymentStatus.INITIATED,
            PaymentStatus.VERIFIED,
            PaymentTransitionTrigger.PROVIDER_PENDING,
        ),
        (
            PaymentStatus.PENDING,
            PaymentStatus.INITIATED,
            PaymentTransitionTrigger.PAYMENT_INITIALIZED,
        ),
        (
            PaymentStatus.REQUIRES_ACTION,
            PaymentStatus.CANCELLED,
            PaymentTransitionTrigger.PROVIDER_FAILED,
        ),
    ],
)
def test_payment_status_transition_rejects_invalid_transition_or_trigger(
    current_status,
    target_status,
    trigger,
):
    with pytest.raises(PaymentLifecycleError):
        transition_payment_status(
            current_status,
            target_status,
            trigger,
            event_source=PaymentEventSource.PAYMENT_PROVIDER_WEBHOOK,
        )


@pytest.mark.parametrize(
    "terminal_status",
    [
        PaymentStatus.VERIFIED,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
        PaymentStatus.EXPIRED,
    ],
)
def test_payment_status_transition_rejects_terminal_source_statuses(
    terminal_status,
):
    with pytest.raises(PaymentLifecycleError):
        transition_payment_status(
            terminal_status,
            PaymentStatus.PENDING,
            PaymentTransitionTrigger.PROVIDER_PENDING,
            event_source=PaymentEventSource.PAYMENT_PROVIDER_WEBHOOK,
        )


@pytest.mark.parametrize(
    "event_source",
    [
        PaymentEventSource.FRONTEND_RETURN,
        PaymentEventSource.PROVIDER_ADAPTER,
    ],
)
def test_frontend_or_provider_adapter_claims_cannot_verify_payment(event_source):
    with pytest.raises(PaymentLifecycleError):
        transition_payment_status(
            PaymentStatus.PENDING,
            PaymentStatus.VERIFIED,
            PaymentTransitionTrigger.VERIFIED_PROVIDER_CONFIRMATION,
            event_source=event_source,
        )


def test_verified_provider_payment_can_confirm_draft_order():
    eligibility = validate_order_confirmation_from_payment(
        PaymentStatus.VERIFIED,
        OrderStatus.DRAFT,
        event_source=PaymentEventSource.PAYMENT_PROVIDER_WEBHOOK,
    )

    assert eligibility.payment_status is PaymentStatus.VERIFIED
    assert eligibility.order_status is OrderStatus.DRAFT
    assert eligibility.event_source is PaymentEventSource.PAYMENT_PROVIDER_WEBHOOK


@pytest.mark.parametrize("payment_status", sorted(FAILED_PAYMENT_STATUSES))
def test_failed_cancelled_or_expired_payments_cannot_confirm_orders(payment_status):
    with pytest.raises(PaymentLifecycleError):
        validate_order_confirmation_from_payment(
            payment_status,
            OrderStatus.DRAFT,
            event_source=PaymentEventSource.PAYMENT_PROVIDER_WEBHOOK,
        )


@pytest.mark.parametrize(
    "payment_status",
    [
        PaymentStatus.INITIATED,
        PaymentStatus.PENDING,
        PaymentStatus.REQUIRES_ACTION,
    ],
)
def test_unverified_payment_statuses_cannot_confirm_orders(payment_status):
    with pytest.raises(PaymentLifecycleError):
        validate_order_confirmation_from_payment(
            payment_status,
            OrderStatus.DRAFT,
            event_source=PaymentEventSource.PAYMENT_PROVIDER_WEBHOOK,
        )


def test_frontend_payment_claims_cannot_confirm_orders():
    with pytest.raises(PaymentLifecycleError):
        validate_order_confirmation_from_payment(
            PaymentStatus.VERIFIED,
            OrderStatus.DRAFT,
            event_source=PaymentEventSource.FRONTEND_RETURN,
        )


def test_verified_payment_cannot_confirm_non_draft_order():
    with pytest.raises(PaymentLifecycleError):
        validate_order_confirmation_from_payment(
            PaymentStatus.VERIFIED,
            OrderStatus.CONFIRMED,
            event_source=PaymentEventSource.PAYMENT_PROVIDER_WEBHOOK,
        )


def test_provider_handoff_eligibility_requires_verified_payment_and_confirmed_order():
    eligibility = validate_provider_handoff_eligibility(
        PaymentStatus.VERIFIED,
        OrderStatus.CONFIRMED,
    )

    assert eligibility.payment_status is PaymentStatus.VERIFIED
    assert eligibility.order_status is OrderStatus.CONFIRMED


@pytest.mark.parametrize(
    ("payment_status", "order_status"),
    [
        (PaymentStatus.PENDING, OrderStatus.CONFIRMED),
        (PaymentStatus.FAILED, OrderStatus.CONFIRMED),
        (PaymentStatus.VERIFIED, OrderStatus.DRAFT),
        (PaymentStatus.VERIFIED, OrderStatus.SENT_TO_PROVIDER),
    ],
)
def test_provider_handoff_eligibility_rejects_unready_payment_or_order_state(
    payment_status,
    order_status,
):
    with pytest.raises(PaymentLifecycleError):
        validate_provider_handoff_eligibility(payment_status, order_status)


def test_invalid_transition_does_not_mutate_caller_owned_payment_state():
    payment_record = MutablePaymentRecord(status=PaymentStatus.PENDING)

    with pytest.raises(PaymentLifecycleError):
        transition_payment_status(
            payment_record.status,
            PaymentStatus.VERIFIED,
            PaymentTransitionTrigger.VERIFIED_PROVIDER_CONFIRMATION,
            event_source=PaymentEventSource.FRONTEND_RETURN,
        )

    assert payment_record.status is PaymentStatus.PENDING


def test_invalid_order_confirmation_does_not_mutate_caller_owned_state():
    payment_record = MutablePaymentRecord(status=PaymentStatus.FAILED)
    order_record = MutableOrderRecord(status=OrderStatus.DRAFT)

    with pytest.raises(PaymentLifecycleError):
        validate_order_confirmation_from_payment(
            payment_record.status,
            order_record.status,
            event_source=PaymentEventSource.PAYMENT_PROVIDER_WEBHOOK,
        )

    assert payment_record.status is PaymentStatus.FAILED
    assert order_record.status is OrderStatus.DRAFT
