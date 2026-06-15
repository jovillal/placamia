import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from app.api.dependencies import get_current_user, get_provider_adapter
from app.core.database import Base, get_db
from app.domain.order_lifecycle import OrderStatus
from app.domain.provider_adapter import (
    AcceptanceDecision,
    AcceptanceResult,
    ProviderOrderState,
)
from app.main import app
from app.models.audit_log import AuditLog
from app.models.order import Order
from app.models.user import User, UserRole
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for provider endpoint tests."""
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
    """Persist one active user for provider endpoint authorization tests."""
    user = User(email=email, full_name="Provider Operator", role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_order(
    db,
    *,
    status: OrderStatus = OrderStatus.SENT_TO_PROVIDER,
) -> Order:
    """Persist one paid sent-to-provider order for endpoint tests."""
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


class RecordingAcceptanceAdapter:
    """Provider adapter test double that records endpoint decisions."""

    def __init__(self, reason_code: str | None = None) -> None:
        """Store optional provider reason returned for rejections."""
        self.reason_code = reason_code
        self.calls: list[tuple[str, AcceptanceDecision]] = []

    def record_acceptance(
        self,
        provider_reference: str,
        decision: AcceptanceDecision,
    ) -> AcceptanceResult:
        """Record the adapter call and return a decision-shaped result."""
        self.calls.append((provider_reference, decision))
        accepted = decision is AcceptanceDecision.ACCEPT
        return AcceptanceResult(
            provider_reference=provider_reference,
            accepted=accepted,
            customer_safe_status=(
                ProviderOrderState.ACCEPTED if accepted else ProviderOrderState.REJECTED
            ),
            reason_code=self.reason_code,
        )


async def post_provider_acceptance(order_id: int, payload: dict[str, object]):
    """Call the provider acceptance endpoint through ASGI test transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post(
            f"/api/v1/provider/orders/{order_id}/acceptance",
            json=payload,
        )


def configure_provider_endpoint_test(db, current_user, provider_adapter) -> None:
    """Install dependency overrides for provider acceptance endpoint tests."""

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_get_current_user():
        return current_user

    async def override_get_provider_adapter():
        return provider_adapter

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_provider_adapter] = override_get_provider_adapter


def table_count(db, model) -> int:
    """Return the number of persisted rows for a model."""
    return db.scalar(select(func.count()).select_from(model))


def test_admin_endpoint_records_provider_acceptance_and_audit_log():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        adapter = RecordingAcceptanceAdapter()
        configure_provider_endpoint_test(db, admin, adapter)

        response = asyncio.run(
            post_provider_acceptance(order.id, {"decision": "accept"})
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload == {
            "order_id": order.id,
            "order_status": OrderStatus.ACCEPTED.value,
            "provider_decision": "accept",
            "customer_safe_status": "accepted",
            "customer_safe_reason_code": None,
            "idempotent": False,
        }
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.ACCEPTED.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at is not None
        assert adapter.calls == [("local-order-1", AcceptanceDecision.ACCEPT)]
        assert table_count(db, AuditLog) == 1
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_admin_endpoint_records_provider_rejection_with_customer_safe_reason():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        adapter = RecordingAcceptanceAdapter(reason_code="provider_timeout")
        configure_provider_endpoint_test(db, admin, adapter)

        response = asyncio.run(
            post_provider_acceptance(order.id, {"decision": "reject"})
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["order_status"] == OrderStatus.CANCELLED.value
        assert payload["customer_safe_status"] == "rejected"
        assert payload["customer_safe_reason_code"] == "provider_unable_to_fulfill"
        assert "provider_timeout" not in response.text
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.CANCELLED.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at is not None
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_non_admin_user_cannot_record_provider_acceptance():
    db = build_session()
    try:
        user = seed_user(db, email="buyer@example.com", role=UserRole.USER)
        order = seed_order(db)
        adapter = RecordingAcceptanceAdapter()
        configure_provider_endpoint_test(db, user, adapter)

        response = asyncio.run(
            post_provider_acceptance(
                order.id,
                {
                    "decision": "accept",
                    "role": "admin",
                    "is_admin": True,
                    "order_status": "accepted",
                },
            )
        )

        assert response.status_code == 403
        assert db.get(Order, order.id).status == OrderStatus.SENT_TO_PROVIDER.value
        assert adapter.calls == []
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_frontend_status_and_reason_claims_are_rejected_without_mutation():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        adapter = RecordingAcceptanceAdapter()
        configure_provider_endpoint_test(db, admin, adapter)

        response = asyncio.run(
            post_provider_acceptance(
                order.id,
                {
                    "decision": "accept",
                    "order_status": "accepted",
                    "reason_code": "trusted_by_frontend",
                    "actor_type": "operator",
                },
            )
        )

        assert response.status_code == 422
        assert db.get(Order, order.id).status == OrderStatus.SENT_TO_PROVIDER.value
        assert adapter.calls == []
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_invalid_lifecycle_state_is_rejected_without_mutation_or_audit_log():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db, status=OrderStatus.CONFIRMED)
        adapter = RecordingAcceptanceAdapter()
        configure_provider_endpoint_test(db, admin, adapter)

        response = asyncio.run(
            post_provider_acceptance(order.id, {"decision": "accept"})
        )

        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "order_not_sent_to_provider"
        assert db.get(Order, order.id).status == OrderStatus.CONFIRMED.value
        assert adapter.calls == []
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_provider_acceptance_endpoint_response_omits_sensitive_fields():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        adapter = RecordingAcceptanceAdapter()
        configure_provider_endpoint_test(db, admin, adapter)

        response = asyncio.run(
            post_provider_acceptance(order.id, {"decision": "accept"})
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
        }
        assert forbidden_fields.isdisjoint(payload)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_audit_failure_rolls_back_provider_acceptance_mutation(monkeypatch):
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(db)
        adapter = RecordingAcceptanceAdapter()
        configure_provider_endpoint_test(db, admin, adapter)

        def reject_audit_recording(*args, **kwargs):
            raise RuntimeError("audit store unavailable")

        monkeypatch.setattr(
            "app.api.v1.endpoints.provider.AuditLogService.record_admin_action",
            reject_audit_recording,
        )

        response = asyncio.run(
            post_provider_acceptance(order.id, {"decision": "accept"})
        )

        assert response.status_code == 500
        assert response.json()["detail"]["code"] == "provider_decision_audit_failed"
        db.expire_all()
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.SENT_TO_PROVIDER.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at is not None
        assert adapter.calls == [("local-order-1", AcceptanceDecision.ACCEPT)]
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()
