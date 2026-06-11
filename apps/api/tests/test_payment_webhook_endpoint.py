import asyncio
import hmac
import json
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

import httpx
from app.core.database import Base, get_db
from app.domain.order_lifecycle import OrderStatus
from app.main import app
from app.models.order import Order
from app.models.user import User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


WEBHOOK_SECRET = "test-payment-webhook-secret"


def build_session():
    """Build an isolated in-memory database session for webhook endpoint tests."""
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


def seed_user(db, email: str = "buyer@example.com") -> User:
    """Persist one user for payment webhook order ownership checks."""
    user = User(email=email, full_name="Test Buyer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_order(
    db,
    user: User,
    *,
    status: OrderStatus = OrderStatus.DRAFT,
    total_amount: str = "40.00",
    currency: str = "COP",
    payment_provider_reference: str | None = None,
    payment_verified_at: datetime | None = None,
    provider_handoff_reference: str | None = None,
) -> Order:
    """Persist one order candidate for webhook confirmation tests."""
    order = Order(
        customer_id=user.id,
        status=status.value,
        subtotal_amount=Decimal(total_amount),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal(total_amount),
        currency=currency,
        payment_provider_reference=payment_provider_reference,
        payment_verified_at=payment_verified_at,
        assigned_provider_id="local-provider",
        provider_handoff_reference=provider_handoff_reference,
        provider_handoff_sent_at=None,
        terms_policy_version="terms-v1",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def raw_payload(**data_overrides) -> bytes:
    """Build a deterministic provider-neutral payment webhook payload."""
    data = {
        "order_id": 1,
        "customer_id": 1,
        "payment_status": "verified",
        "payment_provider_reference": "pay_verified_123",
        "amount": "40.00",
        "currency": "COP",
    }
    data.update(data_overrides)
    payload = {
        "id": "evt_verified_123",
        "type": "payment.verified",
        "data": data,
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def signature_header(raw_body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Return the HMAC-SHA256 signature header for one raw webhook body."""
    signature = hmac.new(secret.encode(), raw_body, sha256).hexdigest()
    return f"sha256={signature}"


def configure_webhook_endpoint_test(db) -> None:
    """Install FastAPI overrides for payment webhook endpoint tests."""

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db


async def post_webhook(raw_body: bytes, signature: str | None):
    """Call the payment webhook endpoint through ASGI test transport."""
    transport = httpx.ASGITransport(app=app)
    headers = {}
    if signature is not None:
        headers["X-Payment-Signature"] = signature
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post(
            "/api/v1/payments/webhook",
            content=raw_body,
            headers=headers,
        )


def assert_webhook_rejection(response, code: str) -> None:
    """Assert a rejected webhook response uses the expected stable code."""
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == code


def assert_order_unchanged(
    db,
    order_id: int,
    *,
    status: OrderStatus = OrderStatus.DRAFT,
) -> None:
    """Assert a rejected webhook did not mutate payment or handoff fields."""
    stored_order = db.get(Order, order_id)
    assert stored_order.status == status.value
    assert stored_order.payment_provider_reference is None
    assert stored_order.payment_verified_at is None
    assert stored_order.provider_handoff_reference is None
    assert stored_order.provider_handoff_sent_at is None


def test_verified_webhook_confirms_draft_order_without_provider_handoff(monkeypatch):
    db = build_session()
    try:
        monkeypatch.setattr("app.api.v1.endpoints.payments.settings.PAYMENT_WEBHOOK_SECRET", WEBHOOK_SECRET)
        user = seed_user(db)
        order = seed_order(db, user)
        raw_body = raw_payload(order_id=order.id, customer_id=user.id)
        configure_webhook_endpoint_test(db)

        response = asyncio.run(post_webhook(raw_body, signature_header(raw_body)))

        assert response.status_code == 200
        payload = response.json()
        assert payload["event_id"] == "evt_verified_123"
        assert payload["order_id"] == order.id
        assert payload["order_status"] == OrderStatus.CONFIRMED.value
        assert payload["payment_provider_reference"] == "pay_verified_123"

        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.CONFIRMED.value
        assert stored_order.payment_provider_reference == "pay_verified_123"
        assert stored_order.payment_verified_at is not None
        assert stored_order.provider_handoff_reference is None
        assert stored_order.provider_handoff_sent_at is None
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_invalid_signature_rejected_without_mutation(monkeypatch):
    db = build_session()
    try:
        monkeypatch.setattr("app.api.v1.endpoints.payments.settings.PAYMENT_WEBHOOK_SECRET", WEBHOOK_SECRET)
        user = seed_user(db)
        order = seed_order(db, user)
        raw_body = raw_payload(order_id=order.id, customer_id=user.id)
        configure_webhook_endpoint_test(db)

        response = asyncio.run(
            post_webhook(raw_body, signature_header(raw_body, "wrong-secret"))
        )

        assert_webhook_rejection(response, "invalid_signature")
        assert_order_unchanged(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_missing_signature_rejected_without_mutation(monkeypatch):
    db = build_session()
    try:
        monkeypatch.setattr("app.api.v1.endpoints.payments.settings.PAYMENT_WEBHOOK_SECRET", WEBHOOK_SECRET)
        user = seed_user(db)
        order = seed_order(db, user)
        raw_body = raw_payload(order_id=order.id, customer_id=user.id)
        configure_webhook_endpoint_test(db)

        response = asyncio.run(post_webhook(raw_body, None))

        assert_webhook_rejection(response, "missing_signature")
        assert_order_unchanged(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_unverified_payment_status_rejected_without_mutation(monkeypatch):
    db = build_session()
    try:
        monkeypatch.setattr("app.api.v1.endpoints.payments.settings.PAYMENT_WEBHOOK_SECRET", WEBHOOK_SECRET)
        user = seed_user(db)
        order = seed_order(db, user)
        raw_body = raw_payload(
            order_id=order.id,
            customer_id=user.id,
            payment_status="failed",
        )
        configure_webhook_endpoint_test(db)

        response = asyncio.run(post_webhook(raw_body, signature_header(raw_body)))

        assert_webhook_rejection(response, "payment_not_verified")
        assert_order_unchanged(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_amount_mismatch_rejected_without_mutation(monkeypatch):
    db = build_session()
    try:
        monkeypatch.setattr("app.api.v1.endpoints.payments.settings.PAYMENT_WEBHOOK_SECRET", WEBHOOK_SECRET)
        user = seed_user(db)
        order = seed_order(db, user, total_amount="40.00")
        raw_body = raw_payload(order_id=order.id, customer_id=user.id, amount="41.00")
        configure_webhook_endpoint_test(db)

        response = asyncio.run(post_webhook(raw_body, signature_header(raw_body)))

        assert_webhook_rejection(response, "payment_amount_mismatch")
        assert_order_unchanged(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_currency_mismatch_rejected_without_mutation(monkeypatch):
    db = build_session()
    try:
        monkeypatch.setattr("app.api.v1.endpoints.payments.settings.PAYMENT_WEBHOOK_SECRET", WEBHOOK_SECRET)
        user = seed_user(db)
        order = seed_order(db, user, currency="COP")
        raw_body = raw_payload(order_id=order.id, customer_id=user.id, currency="USD")
        configure_webhook_endpoint_test(db)

        response = asyncio.run(post_webhook(raw_body, signature_header(raw_body)))

        assert_webhook_rejection(response, "payment_currency_mismatch")
        assert_order_unchanged(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_customer_mismatch_rejected_without_mutation(monkeypatch):
    db = build_session()
    try:
        monkeypatch.setattr("app.api.v1.endpoints.payments.settings.PAYMENT_WEBHOOK_SECRET", WEBHOOK_SECRET)
        user = seed_user(db)
        order = seed_order(db, user)
        raw_body = raw_payload(order_id=order.id, customer_id=user.id + 1)
        configure_webhook_endpoint_test(db)

        response = asyncio.run(post_webhook(raw_body, signature_header(raw_body)))

        assert_webhook_rejection(response, "payment_customer_mismatch")
        assert_order_unchanged(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_already_confirmed_same_reference_is_idempotent(monkeypatch):
    db = build_session()
    try:
        monkeypatch.setattr("app.api.v1.endpoints.payments.settings.PAYMENT_WEBHOOK_SECRET", WEBHOOK_SECRET)
        user = seed_user(db)
        original_verified_at = datetime(2026, 6, 9, tzinfo=UTC)
        order = seed_order(
            db,
            user,
            status=OrderStatus.CONFIRMED,
            payment_provider_reference="pay_verified_123",
            payment_verified_at=original_verified_at,
        )
        original_stored_verified_at = order.payment_verified_at
        raw_body = raw_payload(order_id=order.id, customer_id=user.id)
        configure_webhook_endpoint_test(db)

        response = asyncio.run(post_webhook(raw_body, signature_header(raw_body)))

        assert response.status_code == 200
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.CONFIRMED.value
        assert stored_order.payment_provider_reference == "pay_verified_123"
        assert stored_order.payment_verified_at == original_stored_verified_at
        assert stored_order.provider_handoff_reference is None
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_already_confirmed_same_reference_failed_status_is_rejected(monkeypatch):
    db = build_session()
    try:
        monkeypatch.setattr(
            "app.api.v1.endpoints.payments.settings.PAYMENT_WEBHOOK_SECRET",
            WEBHOOK_SECRET,
        )
        user = seed_user(db)
        order = seed_order(
            db,
            user,
            status=OrderStatus.CONFIRMED,
            payment_provider_reference="pay_verified_123",
            payment_verified_at=datetime(2026, 6, 9, tzinfo=UTC),
        )
        raw_body = raw_payload(
            order_id=order.id,
            customer_id=user.id,
            payment_status="failed",
        )
        configure_webhook_endpoint_test(db)

        response = asyncio.run(post_webhook(raw_body, signature_header(raw_body)))

        assert_webhook_rejection(response, "payment_not_verified")
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.CONFIRMED.value
        assert stored_order.payment_provider_reference == "pay_verified_123"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_already_confirmed_different_reference_is_rejected(monkeypatch):
    db = build_session()
    try:
        monkeypatch.setattr("app.api.v1.endpoints.payments.settings.PAYMENT_WEBHOOK_SECRET", WEBHOOK_SECRET)
        user = seed_user(db)
        order = seed_order(
            db,
            user,
            status=OrderStatus.CONFIRMED,
            payment_provider_reference="pay_original",
            payment_verified_at=datetime(2026, 6, 9, tzinfo=UTC),
        )
        raw_body = raw_payload(order_id=order.id, customer_id=user.id)
        configure_webhook_endpoint_test(db)

        response = asyncio.run(post_webhook(raw_body, signature_header(raw_body)))

        assert_webhook_rejection(response, "payment_reference_conflict")
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.CONFIRMED.value
        assert stored_order.payment_provider_reference == "pay_original"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_webhook_endpoint_appears_in_openapi_schema(monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.payments.settings.PAYMENT_WEBHOOK_SECRET", WEBHOOK_SECRET)

    schema = app.openapi()

    assert "/api/v1/payments/webhook" in schema["paths"]
