from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.database import Base
from app.domain.order_lifecycle import OrderStatus
from app.models.order import Order
from app.repositories.order_repository import OrderRepository
from app.services.order_cancellation_service import (
    OrderCancellationRejected,
    OrderCancellationService,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for cancellation tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    return testing_session_local()


def seed_order(
    db,
    *,
    customer_id: int = 1,
    status: OrderStatus = OrderStatus.CONFIRMED,
    cancellation_requested_from: OrderStatus | None = None,
) -> Order:
    """Persist one paid order candidate for cancellation workflow tests."""
    order = Order(
        customer_id=customer_id,
        status=status.value,
        cancellation_requested_from=(
            cancellation_requested_from.value
            if cancellation_requested_from is not None
            else None
        ),
        subtotal_amount=Decimal("40.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("40.00"),
        currency="COP",
        payment_provider_reference="pay_internal_ref",
        payment_verified_at=datetime(2026, 6, 10, tzinfo=UTC),
        assigned_provider_id="local-provider",
        provider_handoff_reference="local-order-1",
        provider_handoff_sent_at=datetime(2026, 6, 10, tzinfo=UTC),
        terms_policy_version="terms-v1",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def cancellation_service(db):
    """Build the order cancellation service under test."""
    return OrderCancellationService(OrderRepository(db))


class StubOrderRepository:
    """Test double for service-level corrupted-order cancellation tests."""

    def __init__(self, order: Order) -> None:
        """Store one order returned by id lookups."""
        self.order = order

    def get_order_by_id(self, order_id: int) -> Order | None:
        """Return the stored order when the identifier matches."""
        return self.order if self.order.id == order_id else None

    def get_order_for_customer(self, order_id: int, customer_id: int) -> Order | None:
        """Return the stored order when ownership also matches."""
        return (
            self.order
            if self.order.id == order_id and self.order.customer_id == customer_id
            else None
        )

    def resolve_customer_cancellation_request(self, order: Order, *, status: OrderStatus):
        """Fail fast if a corrupted order ever reaches persistence."""
        raise AssertionError("Corrupted cancellation state should not be persisted")


def assert_rejection(exc_info, code: str) -> None:
    """Assert cancellation rejection uses a stable machine-readable code."""
    assert exc_info.value.code == code


@pytest.mark.parametrize(
    "starting_status",
    [
        OrderStatus.CONFIRMED,
        OrderStatus.ACCEPTED,
        OrderStatus.IN_PRODUCTION,
    ],
)
def test_request_cancellation_moves_eligible_paid_order_to_request_state(
    starting_status,
):
    db = build_session()
    try:
        order = seed_order(db, status=starting_status)
        original_payment_verified_at = order.payment_verified_at
        original_provider_handoff_sent_at = order.provider_handoff_sent_at
        service = cancellation_service(db)

        result = service.request_cancellation(order.id, customer_id=order.customer_id)

        stored_order = db.get(Order, order.id)
        assert result.from_status is starting_status
        assert result.target_status is OrderStatus.CANCELLATION_REQUESTED
        assert result.cancellation_requested_from is starting_status
        assert stored_order.status == OrderStatus.CANCELLATION_REQUESTED.value
        assert stored_order.cancellation_requested_from == starting_status.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at == original_payment_verified_at
        assert stored_order.provider_handoff_reference == "local-order-1"
        assert stored_order.provider_handoff_sent_at == original_provider_handoff_sent_at
    finally:
        db.close()


@pytest.mark.parametrize(
    "starting_status",
    [
        OrderStatus.DRAFT,
        OrderStatus.SENT_TO_PROVIDER,
        OrderStatus.READY_FOR_PICKUP,
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
        OrderStatus.CANCELLATION_REQUESTED,
    ],
)
def test_request_cancellation_rejects_ineligible_order_states_without_mutation(
    starting_status,
):
    db = build_session()
    try:
        order = seed_order(
            db,
            status=starting_status,
            cancellation_requested_from=(
                OrderStatus.CONFIRMED
                if starting_status is OrderStatus.CANCELLATION_REQUESTED
                else None
            ),
        )
        service = cancellation_service(db)

        with pytest.raises(OrderCancellationRejected) as exc_info:
            service.request_cancellation(order.id, customer_id=order.customer_id)

        assert_rejection(exc_info, "order_cancellation_not_allowed")
        stored_order = db.get(Order, order.id)
        assert stored_order.status == starting_status.value
    finally:
        db.close()


def test_cross_user_cancellation_request_is_rejected_without_mutation():
    db = build_session()
    try:
        order = seed_order(db, customer_id=1, status=OrderStatus.CONFIRMED)
        service = cancellation_service(db)

        with pytest.raises(OrderCancellationRejected) as exc_info:
            service.request_cancellation(order.id, customer_id=2)

        assert_rejection(exc_info, "order_not_found")
        assert db.get(Order, order.id).status == OrderStatus.CONFIRMED.value
    finally:
        db.close()


def test_admin_approval_moves_pending_request_to_cancelled_without_clearing_history():
    db = build_session()
    try:
        order = seed_order(
            db,
            status=OrderStatus.CANCELLATION_REQUESTED,
            cancellation_requested_from=OrderStatus.ACCEPTED,
        )
        original_payment_verified_at = order.payment_verified_at
        original_provider_handoff_sent_at = order.provider_handoff_sent_at
        service = cancellation_service(db)

        result = service.approve_cancellation(order.id)

        stored_order = db.get(Order, order.id)
        assert result.from_status is OrderStatus.CANCELLATION_REQUESTED
        assert result.target_status is OrderStatus.CANCELLED
        assert result.cancellation_requested_from is OrderStatus.ACCEPTED
        assert stored_order.status == OrderStatus.CANCELLED.value
        assert stored_order.cancellation_requested_from is None
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at == original_payment_verified_at
        assert stored_order.provider_handoff_reference == "local-order-1"
        assert stored_order.provider_handoff_sent_at == original_provider_handoff_sent_at
    finally:
        db.close()


@pytest.mark.parametrize(
    "original_status",
    [
        OrderStatus.CONFIRMED,
        OrderStatus.ACCEPTED,
        OrderStatus.IN_PRODUCTION,
    ],
)
def test_admin_rejection_restores_original_paid_status(original_status):
    db = build_session()
    try:
        order = seed_order(
            db,
            status=OrderStatus.CANCELLATION_REQUESTED,
            cancellation_requested_from=original_status,
        )
        original_payment_verified_at = order.payment_verified_at
        original_provider_handoff_sent_at = order.provider_handoff_sent_at
        service = cancellation_service(db)

        result = service.reject_cancellation(order.id)

        stored_order = db.get(Order, order.id)
        assert result.from_status is OrderStatus.CANCELLATION_REQUESTED
        assert result.target_status is original_status
        assert result.cancellation_requested_from is original_status
        assert stored_order.status == original_status.value
        assert stored_order.cancellation_requested_from is None
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at == original_payment_verified_at
        assert stored_order.provider_handoff_reference == "local-order-1"
        assert stored_order.provider_handoff_sent_at == original_provider_handoff_sent_at
    finally:
        db.close()


@pytest.mark.parametrize(
    "resolution_method",
    ["approve_cancellation", "reject_cancellation"],
)
@pytest.mark.parametrize(
    "stored_original_status",
    ["banana", None],
)
def test_resolution_rejects_corrupted_pending_request_metadata_in_service(
    resolution_method,
    stored_original_status,
):
    order = Order(
        id=1,
        customer_id=1,
        status=OrderStatus.CANCELLATION_REQUESTED.value,
        cancellation_requested_from=stored_original_status,
        subtotal_amount=Decimal("40.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("40.00"),
        currency="COP",
        payment_provider_reference="pay_internal_ref",
        payment_verified_at=datetime(2026, 6, 10, tzinfo=UTC),
        assigned_provider_id="local-provider",
        provider_handoff_reference="local-order-1",
        provider_handoff_sent_at=datetime(2026, 6, 10, tzinfo=UTC),
        terms_policy_version="terms-v1",
    )
    service = OrderCancellationService(StubOrderRepository(order))

    with pytest.raises(OrderCancellationRejected) as exc_info:
        getattr(service, resolution_method)(order.id)

    assert_rejection(exc_info, "invalid_cancellation_requested_from")
    assert order.status == OrderStatus.CANCELLATION_REQUESTED.value
    assert order.cancellation_requested_from == stored_original_status
