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
    """Build an isolated in-memory database session for delivery endpoint tests."""
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
    """Persist one active user for delivery authorization tests."""
    user = User(email=email, full_name="Provider Operator", role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_order(
    db,
    *,
    status: OrderStatus = OrderStatus.SHIPPED,
) -> Order:
    """Persist one paid shipped order for endpoint tests."""
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


async def post_delivery(order_id: int, payload: dict[str, object]):
    """Call the provider delivery endpoint through ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post(
            f"/api/v1/provider/orders/{order_id}/delivery",
            json=payload,
        )


def configure_provider_endpoint_test(db, current_user) -> None:
    """Install dependency overrides for provider delivery endpoint tests."""

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


def test_admin_endpoint_records_delivery_confirmation_and_audit_log():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        configure_provider_endpoint_test(db, admin)

        response = asyncio.run(
            post_delivery(
                order.id,
                {
                    "event": "delivery_confirmed",
                    "event_reference": "delivery-event-1",
                },
            )
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload == {
            "order_id": order.id,
            "order_status": OrderStatus.DELIVERED.value,
            "delivery_event": "delivery_confirmed",
            "customer_safe_status": OrderStatus.DELIVERED.value,
            "event_reference": "delivery-event-1",
            "idempotent": False,
        }
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.DELIVERED.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at is not None
        audit_log = db.scalar(select(AuditLog))
        assert audit_log.event_details["event"] == "delivery_confirmed"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_non_admin_user_cannot_record_delivery():
    db = build_session()
    try:
        user = seed_user(db, email="buyer@example.com", role=UserRole.USER)
        order = seed_order(db)
        configure_provider_endpoint_test(db, user)

        response = asyncio.run(
            post_delivery(
                order.id,
                {
                    "event": "delivery_confirmed",
                    "role": "admin",
                    "is_admin": True,
                    "order_status": "delivered",
                },
            )
        )

        assert response.status_code == 403
        assert db.get(Order, order.id).status == OrderStatus.SHIPPED.value
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
            post_delivery(
                order.id,
                {
                    "event": "delivery_confirmed",
                    "event_reference": "delivery-event-1",
                    "actor_type": "customer",
                    "order_status": "delivered",
                    "reason_code": "trusted_by_frontend",
                },
            )
        )

        assert response.status_code == 422
        assert db.get(Order, order.id).status == OrderStatus.SHIPPED.value
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_invalid_lifecycle_state_is_rejected_without_mutation_or_audit_log():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db, status=OrderStatus.READY_FOR_PICKUP)
        configure_provider_endpoint_test(db, admin)

        response = asyncio.run(post_delivery(order.id, {"event": "delivery_confirmed"}))

        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "order_not_shipped"
        assert db.get(Order, order.id).status == OrderStatus.READY_FOR_PICKUP.value
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
            "event": "delivery_confirmed",
            "event_reference": "delivery-event-1",
        }

        first_response = asyncio.run(post_delivery(order.id, payload))
        second_response = asyncio.run(post_delivery(order.id, payload))

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["idempotent"] is True
        assert db.get(Order, order.id).status == OrderStatus.DELIVERED.value
        assert table_count(db, AuditLog) == 2
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_duplicate_event_reference_with_wrong_state_is_rejected_without_mutation():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db, status=OrderStatus.DELIVERED)
        configure_provider_endpoint_test(db, admin)
        db.add(
            AuditLog(
                actor_user_id=admin.id,
                action="provider.delivery.record",
                resource_type="order",
                resource_id=str(order.id),
                event_details={
                    "event": "delivery_confirmed",
                    "event_reference": "delivery-event-1",
                    "from_status": OrderStatus.SHIPPED.value,
                    "target_status": OrderStatus.DELIVERED.value,
                },
            )
        )
        db.commit()
        order.status = OrderStatus.SHIPPED.value
        db.add(order)
        db.commit()
        db.refresh(order)

        response = asyncio.run(
            post_delivery(
                order.id,
                {
                    "event": "delivery_confirmed",
                    "event_reference": "delivery-event-1",
                },
            )
        )

        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "event_reference_status_conflict"
        assert db.get(Order, order.id).status == OrderStatus.SHIPPED.value
        assert table_count(db, AuditLog) == 1
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_delivery_response_omits_sensitive_fields():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        configure_provider_endpoint_test(db, admin)

        response = asyncio.run(post_delivery(order.id, {"event": "delivery_confirmed"}))

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


def test_audit_failure_rolls_back_delivery_mutation(monkeypatch):
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

        response = asyncio.run(post_delivery(order.id, {"event": "delivery_confirmed"}))

        assert response.status_code == 500
        assert response.json()["detail"]["code"] == "provider_delivery_audit_failed"
        db.expire_all()
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.SHIPPED.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at is not None
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()
