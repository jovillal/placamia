import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from app.api.dependencies import get_current_user
from app.core.database import Base, get_db
from app.domain.order_lifecycle import OrderStatus
from app.main import app
from app.models.audit_log import AuditLog
from app.models.order import Order
from app.models.user import User, UserRole
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for shipment endpoint tests."""
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


def seed_user(db, *, email: str, role: str = UserRole.USER) -> User:
    """Persist one active user for shipment authorization tests."""
    user = User(email=email, full_name="Provider Operator", role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_order(
    db,
    *,
    status: OrderStatus = OrderStatus.READY_FOR_PICKUP,
) -> Order:
    """Persist one paid ready-for-pickup order for endpoint tests."""
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


async def post_shipment(order_id: int, payload: dict[str, object]):
    """Call the provider shipment endpoint through ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post(
            f"/api/v1/provider/orders/{order_id}/shipment",
            json=payload,
        )


def configure_provider_endpoint_test(db, current_user) -> None:
    """Install dependency overrides for provider shipment endpoint tests."""

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_get_current_user():
        return current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user


def table_count(db, model) -> int:
    """Return the number of persisted rows for a model."""
    return db.scalar(select(func.count()).select_from(model))


def test_admin_endpoint_records_qr_pickup_shipment_and_audit_log():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        configure_provider_endpoint_test(db, admin)

        response = asyncio.run(
            post_shipment(
                order.id,
                {
                    "event": "carrier_qr_pickup_scan",
                    "event_reference": "carrier-event-1",
                },
            )
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload == {
            "order_id": order.id,
            "order_status": OrderStatus.SHIPPED.value,
            "shipment_event": "carrier_qr_pickup_scan",
            "customer_safe_status": OrderStatus.SHIPPED.value,
            "event_reference": "carrier-event-1",
            "idempotent": False,
        }
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.SHIPPED.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at is not None
        audit_log = db.scalar(select(AuditLog))
        assert audit_log.event_details["event"] == "carrier_qr_pickup_scan"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_admin_endpoint_records_fallback_shipment_and_audit_log():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        configure_provider_endpoint_test(db, admin)

        response = asyncio.run(
            post_shipment(
                order.id,
                {
                    "event": "authorized_operator_shipment_fallback",
                    "event_reference": "fallback-event-1",
                },
            )
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["order_status"] == OrderStatus.SHIPPED.value
        assert payload["shipment_event"] == "authorized_operator_shipment_fallback"
        assert db.get(Order, order.id).status == OrderStatus.SHIPPED.value
        audit_log = db.scalar(select(AuditLog))
        assert audit_log.event_details["event"] == (
            "authorized_operator_shipment_fallback"
        )
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_non_admin_user_cannot_record_shipment():
    db = build_session()
    try:
        user = seed_user(db, email="buyer@example.com", role=UserRole.USER)
        order = seed_order(db)
        configure_provider_endpoint_test(db, user)

        response = asyncio.run(
            post_shipment(
                order.id,
                {
                    "event": "carrier_qr_pickup_scan",
                    "role": "admin",
                    "is_admin": True,
                    "operator": True,
                    "order_status": "shipped",
                },
            )
        )

        assert response.status_code == 403
        assert db.get(Order, order.id).status == OrderStatus.READY_FOR_PICKUP.value
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_frontend_status_and_actor_claims_are_rejected_without_mutation():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        configure_provider_endpoint_test(db, admin)

        response = asyncio.run(
            post_shipment(
                order.id,
                {
                    "event": "carrier_qr_pickup_scan",
                    "event_reference": "carrier-event-1",
                    "actor_type": "operator",
                    "order_status": "shipped",
                    "reason_code": "trusted_by_frontend",
                },
            )
        )

        assert response.status_code == 422
        assert db.get(Order, order.id).status == OrderStatus.READY_FOR_PICKUP.value
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_invalid_lifecycle_state_is_rejected_without_mutation_or_audit_log():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db, status=OrderStatus.IN_PRODUCTION)
        configure_provider_endpoint_test(db, admin)

        response = asyncio.run(
            post_shipment(order.id, {"event": "carrier_qr_pickup_scan"})
        )

        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "order_not_ready_for_pickup"
        assert db.get(Order, order.id).status == OrderStatus.IN_PRODUCTION.value
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_duplicate_same_event_reference_is_order_state_idempotent_and_audited():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        configure_provider_endpoint_test(db, admin)
        payload = {
            "event": "carrier_qr_pickup_scan",
            "event_reference": "carrier-event-1",
        }

        first_response = asyncio.run(post_shipment(order.id, payload))
        second_response = asyncio.run(post_shipment(order.id, payload))

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["idempotent"] is True
        assert db.get(Order, order.id).status == OrderStatus.SHIPPED.value
        assert table_count(db, AuditLog) == 2
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_conflicting_duplicate_event_reference_is_rejected_without_mutation():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        configure_provider_endpoint_test(db, admin)

        first_response = asyncio.run(
            post_shipment(
                order.id,
                {
                    "event": "carrier_qr_pickup_scan",
                    "event_reference": "shared-event-1",
                },
            )
        )
        second_response = asyncio.run(
            post_shipment(
                order.id,
                {
                    "event": "authorized_operator_shipment_fallback",
                    "event_reference": "shared-event-1",
                },
            )
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 400
        assert second_response.json()["detail"]["code"] == "event_reference_conflict"
        assert db.get(Order, order.id).status == OrderStatus.SHIPPED.value
        assert table_count(db, AuditLog) == 1
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_shipment_response_omits_sensitive_fields():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        configure_provider_endpoint_test(db, admin)

        response = asyncio.run(
            post_shipment(order.id, {"event": "carrier_qr_pickup_scan"})
        )

        assert response.status_code == 200
        payload = response.json()
        forbidden_fields = {
            "customer_id",
            "payment_provider_reference",
            "payment_verified_at",
            "provider_handoff_reference",
            "provider_handoff_sent_at",
            "assigned_provider_id",
            "actor_type",
            "reason_code",
        }
        assert forbidden_fields.isdisjoint(payload)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_audit_failure_rolls_back_shipment_mutation(monkeypatch):
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        configure_provider_endpoint_test(db, admin)

        def reject_audit_recording(*args, **kwargs):
            raise RuntimeError("audit store unavailable")

        monkeypatch.setattr(
            "app.api.v1.endpoints.provider.AuditLogService.record_admin_action",
            reject_audit_recording,
        )

        response = asyncio.run(
            post_shipment(order.id, {"event": "carrier_qr_pickup_scan"})
        )

        assert response.status_code == 500
        assert response.json()["detail"]["code"] == "provider_shipment_audit_failed"
        db.expire_all()
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.READY_FOR_PICKUP.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at is not None
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()
