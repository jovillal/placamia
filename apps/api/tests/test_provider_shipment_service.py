from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.database import Base
from app.domain.order_lifecycle import OrderStatus
from app.domain.provider_shipment import ProviderShipmentEvent
from app.models.audit_log import AuditLog
from app.models.order import Order
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.order_repository import OrderRepository
from app.services.provider_shipment_service import (
    PROVIDER_SHIPMENT_AUDIT_ACTION,
    ProviderShipmentRejected,
    ProviderShipmentService,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for shipment tests."""
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
    status: OrderStatus = OrderStatus.READY_FOR_PICKUP,
) -> Order:
    """Persist one paid ready-for-pickup order candidate."""
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


def seed_shipment_audit(
    db,
    order: Order,
    *,
    event: ProviderShipmentEvent,
    event_reference: str,
    from_status: OrderStatus,
    target_status: OrderStatus,
) -> None:
    """Persist one prior shipment audit event."""
    db.add(
        AuditLog(
            actor_user_id=1,
            action=PROVIDER_SHIPMENT_AUDIT_ACTION,
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


def shipment_service(db):
    """Build the provider shipment service under test."""
    return ProviderShipmentService(
        OrderRepository(db),
        AuditLogRepository(db),
    )


def assert_rejection(exc_info, code: str) -> None:
    """Assert shipment rejection uses a stable code."""
    assert exc_info.value.code == code


def test_qr_pickup_scan_moves_ready_order_to_shipped():
    db = build_session()
    try:
        order = seed_order(db)
        original_payment_verified_at = order.payment_verified_at
        service = shipment_service(db)

        result = service.process_shipment(
            order.id,
            ProviderShipmentEvent.CARRIER_QR_PICKUP_SCAN,
            event_reference="carrier-event-1",
        )

        stored_order = db.get(Order, order.id)
        assert result.order.status == OrderStatus.SHIPPED.value
        assert result.from_status is OrderStatus.READY_FOR_PICKUP
        assert result.target_status is OrderStatus.SHIPPED
        assert result.event_reference == "carrier-event-1"
        assert result.idempotent is False
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at == original_payment_verified_at
    finally:
        db.close()


def test_admin_fallback_moves_ready_order_to_shipped():
    db = build_session()
    try:
        order = seed_order(db)
        service = shipment_service(db)

        result = service.process_shipment(
            order.id,
            ProviderShipmentEvent.AUTHORIZED_OPERATOR_SHIPMENT_FALLBACK,
            event_reference="fallback-event-1",
        )

        assert result.order.status == OrderStatus.SHIPPED.value
        assert result.from_status is OrderStatus.READY_FOR_PICKUP
        assert result.target_status is OrderStatus.SHIPPED
        assert result.idempotent is False
    finally:
        db.close()


def test_invalid_shipment_state_is_rejected_without_mutation():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.IN_PRODUCTION)
        service = shipment_service(db)

        with pytest.raises(ProviderShipmentRejected) as exc_info:
            service.process_shipment(
                order.id,
                ProviderShipmentEvent.CARRIER_QR_PICKUP_SCAN,
            )

        assert_rejection(exc_info, "order_not_ready_for_pickup")
        assert db.get(Order, order.id).status == OrderStatus.IN_PRODUCTION.value
    finally:
        db.close()


def test_duplicate_same_shipment_reference_is_order_state_idempotent():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.SHIPPED)
        seed_shipment_audit(
            db,
            order,
            event=ProviderShipmentEvent.CARRIER_QR_PICKUP_SCAN,
            event_reference="carrier-event-1",
            from_status=OrderStatus.READY_FOR_PICKUP,
            target_status=OrderStatus.SHIPPED,
        )
        service = shipment_service(db)

        result = service.process_shipment(
            order.id,
            ProviderShipmentEvent.CARRIER_QR_PICKUP_SCAN,
            event_reference="carrier-event-1",
        )

        assert result.idempotent is True
        assert result.order.status == OrderStatus.SHIPPED.value
        assert result.from_status is OrderStatus.READY_FOR_PICKUP
        assert db.get(Order, order.id).status == OrderStatus.SHIPPED.value
    finally:
        db.close()


def test_conflicting_duplicate_shipment_reference_is_rejected_without_mutation():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.SHIPPED)
        seed_shipment_audit(
            db,
            order,
            event=ProviderShipmentEvent.CARRIER_QR_PICKUP_SCAN,
            event_reference="shared-event-1",
            from_status=OrderStatus.READY_FOR_PICKUP,
            target_status=OrderStatus.SHIPPED,
        )
        service = shipment_service(db)

        with pytest.raises(ProviderShipmentRejected) as exc_info:
            service.process_shipment(
                order.id,
                ProviderShipmentEvent.AUTHORIZED_OPERATOR_SHIPMENT_FALLBACK,
                event_reference="shared-event-1",
            )

        assert_rejection(exc_info, "event_reference_conflict")
        assert db.get(Order, order.id).status == OrderStatus.SHIPPED.value
    finally:
        db.close()
