from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.database import Base
from app.domain.order_lifecycle import OrderStatus
from app.domain.provider_production_progress import ProviderProductionProgressEvent
from app.models.audit_log import AuditLog
from app.models.order import Order
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.order_repository import OrderRepository
from app.services.provider_production_progress_service import (
    PROVIDER_PRODUCTION_PROGRESS_AUDIT_ACTION,
    ProviderProductionProgressRejected,
    ProviderProductionProgressService,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for production progress."""
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
    status: OrderStatus = OrderStatus.ACCEPTED,
) -> Order:
    """Persist one paid provider-accepted order candidate."""
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


def seed_production_progress_audit(
    db,
    order: Order,
    *,
    event: ProviderProductionProgressEvent,
    event_reference: str,
    from_status: OrderStatus,
    target_status: OrderStatus,
) -> None:
    """Persist one prior production progress audit event."""
    db.add(
        AuditLog(
            actor_user_id=1,
            action=PROVIDER_PRODUCTION_PROGRESS_AUDIT_ACTION,
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


def production_progress_service(db):
    """Build the provider production progress service under test."""
    return ProviderProductionProgressService(
        OrderRepository(db),
        AuditLogRepository(db),
    )


def assert_rejection(exc_info, code: str) -> None:
    """Assert production progress rejection uses a stable code."""
    assert exc_info.value.code == code


def test_production_started_moves_accepted_order_to_in_production():
    db = build_session()
    try:
        order = seed_order(db)
        original_payment_verified_at = order.payment_verified_at
        service = production_progress_service(db)

        result = service.process_production_progress(
            order.id,
            ProviderProductionProgressEvent.PRODUCTION_STARTED,
            event_reference="provider-event-1",
        )

        stored_order = db.get(Order, order.id)
        assert result.order.status == OrderStatus.IN_PRODUCTION.value
        assert result.from_status is OrderStatus.ACCEPTED
        assert result.target_status is OrderStatus.IN_PRODUCTION
        assert result.event_reference == "provider-event-1"
        assert result.idempotent is False
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at == original_payment_verified_at
    finally:
        db.close()


def test_package_ready_moves_in_production_order_to_ready_for_pickup():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.IN_PRODUCTION)
        service = production_progress_service(db)

        result = service.process_production_progress(
            order.id,
            ProviderProductionProgressEvent.PACKAGE_READY_FOR_PICKUP,
            event_reference="provider-event-2",
        )

        assert result.order.status == OrderStatus.READY_FOR_PICKUP.value
        assert result.from_status is OrderStatus.IN_PRODUCTION
        assert result.target_status is OrderStatus.READY_FOR_PICKUP
        assert result.idempotent is False
    finally:
        db.close()


def test_invalid_production_progress_state_is_rejected_without_mutation():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.CONFIRMED)
        service = production_progress_service(db)

        with pytest.raises(ProviderProductionProgressRejected) as exc_info:
            service.process_production_progress(
                order.id,
                ProviderProductionProgressEvent.PRODUCTION_STARTED,
            )

        assert_rejection(exc_info, "order_not_accepted")
        assert db.get(Order, order.id).status == OrderStatus.CONFIRMED.value
    finally:
        db.close()


def test_duplicate_same_event_reference_is_order_state_idempotent_without_mutation():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.IN_PRODUCTION)
        seed_production_progress_audit(
            db,
            order,
            event=ProviderProductionProgressEvent.PRODUCTION_STARTED,
            event_reference="provider-event-1",
            from_status=OrderStatus.ACCEPTED,
            target_status=OrderStatus.IN_PRODUCTION,
        )
        service = production_progress_service(db)

        result = service.process_production_progress(
            order.id,
            ProviderProductionProgressEvent.PRODUCTION_STARTED,
            event_reference="provider-event-1",
        )

        assert result.idempotent is True
        assert result.order.status == OrderStatus.IN_PRODUCTION.value
        assert result.from_status is OrderStatus.ACCEPTED
        assert db.get(Order, order.id).status == OrderStatus.IN_PRODUCTION.value
    finally:
        db.close()


def test_conflicting_duplicate_event_reference_is_rejected_without_mutation():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.IN_PRODUCTION)
        seed_production_progress_audit(
            db,
            order,
            event=ProviderProductionProgressEvent.PRODUCTION_STARTED,
            event_reference="provider-event-1",
            from_status=OrderStatus.ACCEPTED,
            target_status=OrderStatus.IN_PRODUCTION,
        )
        service = production_progress_service(db)

        with pytest.raises(ProviderProductionProgressRejected) as exc_info:
            service.process_production_progress(
                order.id,
                ProviderProductionProgressEvent.PACKAGE_READY_FOR_PICKUP,
                event_reference="provider-event-1",
            )

        assert_rejection(exc_info, "event_reference_conflict")
        assert db.get(Order, order.id).status == OrderStatus.IN_PRODUCTION.value
    finally:
        db.close()
