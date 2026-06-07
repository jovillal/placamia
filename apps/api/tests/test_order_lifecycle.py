import pytest
from app.domain.order_lifecycle import (
    CANCELLATION_REQUESTABLE_STATUSES,
    ORDER_STATUS_TRANSITIONS,
    TERMINAL_ORDER_STATUSES,
    OrderStatus,
    OrderStatusTransitionError,
    OrderTransitionTrigger,
    transition_order_status,
)


@pytest.mark.parametrize(
    ("current_status", "target_status", "trigger"),
    [
        (
            OrderStatus.DRAFT,
            OrderStatus.CONFIRMED,
            OrderTransitionTrigger.VERIFIED_PAYMENT,
        ),
        (
            OrderStatus.CONFIRMED,
            OrderStatus.SENT_TO_PROVIDER,
            OrderTransitionTrigger.PROVIDER_HANDOFF_SENT,
        ),
        (
            OrderStatus.SENT_TO_PROVIDER,
            OrderStatus.ACCEPTED,
            OrderTransitionTrigger.PROVIDER_ACCEPTED,
        ),
        (
            OrderStatus.ACCEPTED,
            OrderStatus.IN_PRODUCTION,
            OrderTransitionTrigger.PRODUCTION_STARTED,
        ),
        (
            OrderStatus.IN_PRODUCTION,
            OrderStatus.READY_FOR_PICKUP,
            OrderTransitionTrigger.PACKAGE_READY_FOR_PICKUP,
        ),
        (
            OrderStatus.READY_FOR_PICKUP,
            OrderStatus.SHIPPED,
            OrderTransitionTrigger.CARRIER_QR_PICKUP_SCAN,
        ),
        (
            OrderStatus.READY_FOR_PICKUP,
            OrderStatus.SHIPPED,
            OrderTransitionTrigger.AUTHORIZED_OPERATOR_SHIPMENT_FALLBACK,
        ),
        (
            OrderStatus.SHIPPED,
            OrderStatus.DELIVERED,
            OrderTransitionTrigger.DELIVERY_CONFIRMED,
        ),
    ],
)
def test_order_lifecycle_allows_canonical_path_a_transitions(
    current_status,
    target_status,
    trigger,
):
    transition = transition_order_status(current_status, target_status, trigger)

    assert transition.from_status is current_status
    assert transition.to_status is target_status
    assert transition.trigger is trigger


def test_draft_to_confirmed_requires_verified_payment_trigger():
    current_status = OrderStatus.DRAFT

    with pytest.raises(OrderStatusTransitionError):
        transition_order_status(
            current_status,
            OrderStatus.CONFIRMED,
            OrderTransitionTrigger.PROVIDER_HANDOFF_SENT,
        )

    assert current_status is OrderStatus.DRAFT


def test_provider_handoff_happens_only_after_confirmed_order():
    current_status = OrderStatus.DRAFT

    with pytest.raises(OrderStatusTransitionError):
        transition_order_status(
            current_status,
            OrderStatus.SENT_TO_PROVIDER,
            OrderTransitionTrigger.PROVIDER_HANDOFF_SENT,
        )

    assert current_status is OrderStatus.DRAFT


def test_provider_acceptance_and_rejection_happen_only_after_handoff():
    invalid_current_status = OrderStatus.CONFIRMED

    with pytest.raises(OrderStatusTransitionError):
        transition_order_status(
            invalid_current_status,
            OrderStatus.ACCEPTED,
            OrderTransitionTrigger.PROVIDER_ACCEPTED,
        )

    with pytest.raises(OrderStatusTransitionError):
        transition_order_status(
            invalid_current_status,
            OrderStatus.CANCELLED,
            OrderTransitionTrigger.PROVIDER_REJECTED,
        )

    assert invalid_current_status is OrderStatus.CONFIRMED


def test_provider_rejection_from_sent_to_provider_cancels_order():
    transition = transition_order_status(
        OrderStatus.SENT_TO_PROVIDER,
        OrderStatus.CANCELLED,
        OrderTransitionTrigger.PROVIDER_REJECTED,
    )

    assert transition.to_status is OrderStatus.CANCELLED


@pytest.mark.parametrize("current_status", sorted(CANCELLATION_REQUESTABLE_STATUSES))
def test_paid_customer_cancellation_moves_to_request_state(current_status):
    transition = transition_order_status(
        current_status,
        OrderStatus.CANCELLATION_REQUESTED,
        OrderTransitionTrigger.CUSTOMER_CANCELLATION_REQUESTED,
    )

    assert transition.to_status is OrderStatus.CANCELLATION_REQUESTED


def test_customer_cancellation_request_does_not_directly_cancel_paid_order():
    current_status = OrderStatus.CONFIRMED

    with pytest.raises(OrderStatusTransitionError):
        transition_order_status(
            current_status,
            OrderStatus.CANCELLED,
            OrderTransitionTrigger.CUSTOMER_CANCELLATION_REQUESTED,
        )

    assert current_status is OrderStatus.CONFIRMED


@pytest.mark.parametrize("previous_status", sorted(CANCELLATION_REQUESTABLE_STATUSES))
def test_cancellation_rejection_returns_to_original_paid_status(previous_status):
    transition = transition_order_status(
        OrderStatus.CANCELLATION_REQUESTED,
        previous_status,
        OrderTransitionTrigger.CANCELLATION_REJECTED,
        cancellation_requested_from=previous_status,
    )

    assert transition.to_status is previous_status


def test_cancellation_rejection_requires_original_paid_status():
    current_status = OrderStatus.CANCELLATION_REQUESTED

    with pytest.raises(OrderStatusTransitionError):
        transition_order_status(
            current_status,
            OrderStatus.ACCEPTED,
            OrderTransitionTrigger.CANCELLATION_REJECTED,
            cancellation_requested_from=OrderStatus.CONFIRMED,
        )

    assert current_status is OrderStatus.CANCELLATION_REQUESTED


def test_approved_cancellation_request_cancels_order():
    transition = transition_order_status(
        OrderStatus.CANCELLATION_REQUESTED,
        OrderStatus.CANCELLED,
        OrderTransitionTrigger.CANCELLATION_APPROVED,
    )

    assert transition.to_status is OrderStatus.CANCELLED


def test_ready_for_pickup_to_shipped_requires_qr_scan_or_operator_fallback():
    current_status = OrderStatus.READY_FOR_PICKUP

    with pytest.raises(OrderStatusTransitionError):
        transition_order_status(
            current_status,
            OrderStatus.SHIPPED,
            OrderTransitionTrigger.DELIVERY_CONFIRMED,
        )

    assert current_status is OrderStatus.READY_FOR_PICKUP


@pytest.mark.parametrize("terminal_status", sorted(TERMINAL_ORDER_STATUSES))
def test_terminal_statuses_do_not_transition(terminal_status):
    with pytest.raises(OrderStatusTransitionError):
        transition_order_status(
            terminal_status,
            OrderStatus.CONFIRMED,
            OrderTransitionTrigger.VERIFIED_PAYMENT,
        )


def test_every_transition_is_backed_by_a_specific_backend_trigger():
    assert ORDER_STATUS_TRANSITIONS
    for triggers in ORDER_STATUS_TRANSITIONS.values():
        assert triggers
        assert all(isinstance(trigger, OrderTransitionTrigger) for trigger in triggers)
