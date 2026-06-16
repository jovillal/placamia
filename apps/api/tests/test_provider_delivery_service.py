from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.database import Base
from app.domain.order_lifecycle import OrderStatus
from app.domain.provider_delivery import ProviderDeliveryEvent
from app.models.audit_log import AuditLog
from app.models.order import Order
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.order_repository import OrderRepository
from app.services.provider_delivery_service import (
    PROVIDER_DELIVERY_AUDIT_ACTION,
    ProviderDeliveryRejected,
    ProviderDeliveryService,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for delivery tests."""
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
    status: OrderStatus = OrderStatus.SHIPPED,
) -> Order:
    """Persist one paid shipped order candidate."""
    order = Order(
        customer_id=1,
        status=status.value,
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


def seed_delivery_audit(
    db,
    order: Order,
    *,
    event: ProviderDeliveryEvent,
    event_reference: str,
    from_status: OrderStatus,
    target_status: OrderStatus,
) -> None:
    """Persist one prior delivery audit event."""
    db.add(
        AuditLog(
            actor_user_id=1,
            action=PROVIDER_DELIVERY_AUDIT_ACTION,
            resource_type="order",
            resource_id=str(order.id),
            event_details={
                "event": event.value,
                "event_reference": event_reference,
                "from_status": from_status.value,
                "target_status": target_status.value,
            },
        )
    )
    db.commit()


def delivery_service(db):
    """Build the provider delivery service under test."""
    return ProviderDeliveryService(
        OrderRepository(db),
        AuditLogRepository(db),
    )


def assert_rejection(exc_info, code: str) -> None:
    """Assert delivery rejection uses a stable code."""
    assert exc_info.value.code == code


def test_delivery_confirmation_moves_shipped_order_to_delivered():
    db = build_session()
    try:
        order = seed_order(db)
        original_payment_verified_at = order.payment_verified_at
        service = delivery_service(db)

        result = service.process_delivery(
            order.id,
            ProviderDeliveryEvent.DELIVERY_CONFIRMED,
            event_reference="delivery-event-1",
        )

        stored_order = db.get(Order, order.id)
        assert result.order.status == OrderStatus.DELIVERED.value
        assert result.from_status is OrderStatus.SHIPPED
        assert result.target_status is OrderStatus.DELIVERED
        assert result.event_reference == "delivery-event-1"
        assert result.idempotent is False
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at == original_payment_verified_at
    finally:
        db.close()


def test_invalid_delivery_state_is_rejected_without_mutation():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.READY_FOR_PICKUP)
        service = delivery_service(db)

        with pytest.raises(ProviderDeliveryRejected) as exc_info:
            service.process_delivery(
                order.id,
                ProviderDeliveryEvent.DELIVERY_CONFIRMED,
            )

        assert_rejection(exc_info, "order_not_shipped")
        assert db.get(Order, order.id).status == OrderStatus.READY_FOR_PICKUP.value
    finally:
        db.close()


def test_duplicate_same_delivery_reference_is_order_state_idempotent():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.DELIVERED)
        seed_delivery_audit(
            db,
            order,
            event=ProviderDeliveryEvent.DELIVERY_CONFIRMED,
            event_reference="delivery-event-1",
            from_status=OrderStatus.SHIPPED,
            target_status=OrderStatus.DELIVERED,
        )
        service = delivery_service(db)

        result = service.process_delivery(
            order.id,
            ProviderDeliveryEvent.DELIVERY_CONFIRMED,
            event_reference="delivery-event-1",
        )

        assert result.idempotent is True
        assert result.order.status == OrderStatus.DELIVERED.value
        assert result.from_status is OrderStatus.SHIPPED
        assert db.get(Order, order.id).status == OrderStatus.DELIVERED.value
    finally:
        db.close()


def test_duplicate_delivery_reference_with_wrong_state_is_rejected():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.SHIPPED)
        seed_delivery_audit(
            db,
            order,
            event=ProviderDeliveryEvent.DELIVERY_CONFIRMED,
            event_reference="delivery-event-1",
            from_status=OrderStatus.SHIPPED,
            target_status=OrderStatus.DELIVERED,
        )
        service = delivery_service(db)

        with pytest.raises(ProviderDeliveryRejected) as exc_info:
            service.process_delivery(
                order.id,
                ProviderDeliveryEvent.DELIVERY_CONFIRMED,
                event_reference="delivery-event-1",
            )

        assert_rejection(exc_info, "event_reference_status_conflict")
        assert db.get(Order, order.id).status == OrderStatus.SHIPPED.value
    finally:
        db.close()
