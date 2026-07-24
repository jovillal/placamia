import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from app.api.dependencies import (
    get_current_user,
    get_payment_provider_runtime_factory,
    get_provider_adapter,
)
from app.core.config import settings
from app.core.database import Base, get_db
from app.domain.order_lifecycle import OrderStatus
from app.domain.payment_lifecycle import PaymentStatus
from app.domain.provider_adapter import (
    AvailabilityState,
    CatalogItemType,
    LocalMockProviderAdapter,
    LocalProviderFixture,
)
from app.main import app
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.payment_provider_event import PaymentProviderEvent
from app.models.payment_provider_transaction import PaymentProviderTransaction
from app.models.payment_webhook_event import PaymentWebhookEvent
from app.models.product import Product
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.services.payment_initialization_service import PaymentInitializationService
from app.services.payment_provider_registry import (
    ConfiguredPaymentProviderRuntimeFactory,
    PaymentProviderRegistry,
    PaymentProviderRuntime,
)
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for payment endpoint tests."""
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
    """Persist one active user for authenticated payment tests."""
    user = User(email=email, full_name="Payment Buyer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_product(db) -> Product:
    """Persist one Product referenced by payment-ready OrderItem snapshots."""
    category = Category(name="Emergency", description=None)
    product = Product(
        name="Emergency exit sign",
        description="Catalog description",
        category=category,
        base_price=Decimal("20.00"),
        is_active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def seed_order(
    db,
    user: User,
    *,
    status: OrderStatus = OrderStatus.DRAFT,
    total_amount: str = "40.00",
    currency: str = "COP",
) -> Order:
    """Persist one customer Order candidate for payment initialization."""
    order = Order(
        customer_id=user.id,
        status=status.value,
        subtotal_amount=Decimal(total_amount),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal(total_amount),
        currency=currency,
        assigned_provider_id="local-provider",
        terms_policy_version="terms-v1",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def add_payment_ready_item(
    db,
    order: Order,
    product: Product,
    *,
    total_amount: str = "40.00",
    provider_pricing_reference: str | None = "local-quote-product-1",
) -> None:
    """Attach one provider-ready immutable item snapshot to an Order."""
    order.items = [
        OrderItem(
            item_type="product",
            product_id=product.id,
            display_name="Snapshot product name",
            customer_safe_description="Snapshot description",
            selected_options={},
            quantity=2,
            unit_price_amount=Decimal("20.00"),
            line_subtotal_amount=Decimal(total_amount),
            line_discount_amount=Decimal("0.00"),
            line_tax_amount=Decimal("0.00"),
            line_total_amount=Decimal(total_amount),
            currency=order.currency,
            assigned_provider_id="local-provider",
            provider_pricing_reference=provider_pricing_reference,
            provider_payload_snapshot={
                "item_type": "product",
                "product_id": product.id,
                "display_name": "Snapshot product name",
                "selected_options": {},
                "quantity": 2,
                "provider_quote_reference": provider_pricing_reference,
            },
        )
    ]
    db.add(order)
    db.commit()
    db.refresh(order)


def seed_payment(
    db,
    order: Order,
    *,
    status: PaymentStatus,
    amount: str = "40.00",
    provider_code: str = "legacy_generic",
    checkout_expires_at=None,
) -> Payment:
    """Persist one Payment for initialization idempotency tests."""
    payment = Payment(
        order_id=order.id,
        provider_code=provider_code,
        merchant_reference=(
            f"placamia-seeded-{order.id}-{status.value}"
            if provider_code == "wompi"
            else f"legacy-seeded-{order.id}-{status.value}"
        ),
        status=status.value,
        amount=Decimal(amount),
        currency=order.currency,
        checkout_expires_at=checkout_expires_at,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def configure_payment_endpoint_test(db, current_user: User | None = None) -> None:
    """Install FastAPI dependency overrides for payment endpoint tests."""

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    async def override_get_provider_adapter():
        return LocalMockProviderAdapter(
            {
                (CatalogItemType.PRODUCT, product.id): available_provider_fixture()
                for product in db.query(Product).all()
            }
        )

    app.dependency_overrides[get_provider_adapter] = override_get_provider_adapter

    async def override_get_payment_provider_runtime_factory():
        return ConfiguredPaymentProviderRuntimeFactory(ValidPaymentSettings())

    app.dependency_overrides[get_payment_provider_runtime_factory] = (
        override_get_payment_provider_runtime_factory
    )

    if current_user is not None:

        async def override_get_current_user():
            return current_user

        app.dependency_overrides[get_current_user] = override_get_current_user


def available_provider_fixture() -> LocalProviderFixture:
    """Return a direct-checkout eligible provider fixture."""
    return LocalProviderFixture(
        availability_state=AvailabilityState.AVAILABLE,
        provider_cost=Decimal("12.00"),
        supports_requested_configuration=True,
    )


class ValidPaymentSettings:
    """Safe deterministic Wompi sandbox settings for endpoint tests."""

    ENV = "test"
    PAYMENT_PROVIDER_DEFAULT = "wompi"
    PAYMENT_RETURN_URL = "http://localhost:3000/payments/return"
    PAYMENT_CHECKOUT_TTL_SECONDS = "1800"
    WOMPI_ENVIRONMENT = "sandbox"
    WOMPI_PUBLIC_KEY = "pub_test_endpoint-key"
    WOMPI_INTEGRITY_SECRET = "test_integrity_endpoint-secret"


def configure_provider_adapter(db, fixtures) -> None:
    """Override the provider adapter with test-controlled fixtures."""

    async def override_get_provider_adapter():
        return LocalMockProviderAdapter(fixtures)

    app.dependency_overrides[get_provider_adapter] = override_get_provider_adapter


def configure_payment_runtime_factory(factory) -> None:
    """Override lazy payment-provider runtime creation for one test."""

    async def override_get_payment_provider_runtime_factory():
        return factory

    app.dependency_overrides[get_payment_provider_runtime_factory] = (
        override_get_payment_provider_runtime_factory
    )


async def post_payment(
    payload: dict[str, object],
    *,
    headers: dict[str, str] | None = None,
):
    """Call the payment initialization endpoint through ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post("/api/v1/payments", json=payload, headers=headers)


def table_count(db, model) -> int:
    """Return the number of persisted rows for a model."""
    return db.scalar(select(func.count()).select_from(model))


def payments_for_order(db, order_id: int) -> list[Payment]:
    """Return persisted Payments for one Order sorted by id."""
    return (
        db.query(Payment)
        .filter(Payment.order_id == order_id)
        .order_by(Payment.id.asc())
        .all()
    )


def assert_payment_rejection(response, code: str, status_code: int = 400) -> None:
    """Assert a payment endpoint response contains a stable rejection code."""
    assert response.status_code == status_code
    assert response.json()["detail"]["code"] == code


def assert_no_payment_or_order_mutation(db, order_id: int) -> None:
    """Assert payment initialization rejection left payment and order state alone."""
    stored_order = db.get(Order, order_id)
    assert stored_order.status == OrderStatus.DRAFT.value
    assert stored_order.payment_provider_reference is None
    assert stored_order.payment_verified_at is None
    assert stored_order.provider_handoff_reference is None
    assert stored_order.provider_handoff_sent_at is None
    assert payments_for_order(db, order_id) == []


def test_initialize_payment_creates_wompi_handoff_from_backend_order_state(
    caplog,
):
    db = build_session()
    try:
        caplog.set_level(logging.INFO, logger="sqlalchemy.engine.Engine")
        db.bind.echo = True
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert response.status_code == 201
        payload = response.json()["data"]
        assert payload["payment_id"] == 1
        assert payload["order_id"] == order.id
        assert payload["payment_status"] == PaymentStatus.REQUIRES_ACTION.value
        assert payload["amount"] == "40.00"
        assert payload["currency"] == "COP"
        assert payload["handoff"]["type"] == "redirect"
        assert payload["checkout_expires_at"].endswith("Z")
        parsed_handoff = urlparse(payload["handoff"]["url"])
        assert parsed_handoff.netloc == "checkout.wompi.co"
        parsed_query = parse_qs(parsed_handoff.query)
        assert set(parsed_query) == {
            "public-key",
            "currency",
            "amount-in-cents",
            "reference",
            "signature:integrity",
            "redirect-url",
            "expiration-time",
        }
        assert "-uncommitted-" not in response.text

        payments = payments_for_order(db, order.id)
        assert len(payments) == 1
        assert payments[0].status == PaymentStatus.REQUIRES_ACTION.value
        assert payments[0].amount == Decimal("40.00")
        assert payments[0].currency == "COP"
        assert payments[0].provider_code == "wompi"
        assert payments[0].merchant_reference == (f"placamia-payment-{payments[0].id}")
        assert payments[0].merchant_reference in caplog.text
        assert payments[0].checkout_expires_at is not None
        assert payments[0].payment_provider_reference is None
        assert payments[0].verified_at is None

        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.DRAFT.value
        assert stored_order.payment_provider_reference is None
        assert stored_order.payment_verified_at is None
        assert stored_order.provider_handoff_reference is None
        assert stored_order.provider_handoff_sent_at is None
        assert db.scalars(select(AuditLog)).all() == []
        assert "-uncommitted-" not in caplog.text
        assert ValidPaymentSettings.WOMPI_INTEGRITY_SECRET not in caplog.text
        assert payload["handoff"]["url"] not in caplog.text
        signature_preimage = (
            f"{payments[0].merchant_reference}"
            f"{parsed_query['amount-in-cents'][0]}"
            f"{payments[0].currency}"
            f"{parsed_query['expiration-time'][0]}"
            f"{ValidPaymentSettings.WOMPI_INTEGRITY_SECRET}"
        )
        assert signature_preimage not in caplog.text
        assert parsed_query["signature:integrity"][0] not in caplog.text
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_payment_service_uses_injected_clock_for_exact_thirty_minute_expiration():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        fixed_now = datetime(2026, 7, 24, 12, 0, 0, 123456, tzinfo=UTC)
        provider_adapter = LocalMockProviderAdapter(
            {
                (CatalogItemType.PRODUCT, product.id): available_provider_fixture(),
            }
        )
        service = PaymentInitializationService(
            OrderRepository(db),
            PaymentRepository(db),
            provider_adapter,
            ConfiguredPaymentProviderRuntimeFactory(ValidPaymentSettings()),
            clock=lambda: fixed_now,
        )

        result = asyncio.run(
            service.initialize_payment(order_id=order.id, current_user=user)
        )

        assert result.payment.checkout_expires_at.replace(tzinfo=UTC) == datetime(
            2026,
            7,
            24,
            12,
            30,
            0,
            123000,
            tzinfo=UTC,
        )
        assert result.checkout_session.expires_at == datetime(
            2026,
            7,
            24,
            12,
            30,
            0,
            123000,
            tzinfo=UTC,
        )
        query = parse_qs(urlparse(result.checkout_session.handoff.url).query)
        assert query["expiration-time"] == ["2026-07-24T12:30:00.123Z"]
    finally:
        db.rollback()
        db.close()


def test_initialize_payment_rejects_unauthenticated_access_without_mutation():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        configure_payment_endpoint_test(db)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert response.status_code == 401
        assert_no_payment_or_order_mutation(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_initialize_payment_rejects_invalid_token_without_mutation(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_TOKEN_SECRET", "test-token-secret")
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        configure_payment_endpoint_test(db)

        response = asyncio.run(
            post_payment(
                {"order_id": order.id},
                headers={"Authorization": "Bearer invalid-token"},
            )
        )

        assert response.status_code == 401
        assert_no_payment_or_order_mutation(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_authentication_precedes_forbidden_payment_claim_rejection():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        configure_payment_endpoint_test(db)

        response = asyncio.run(post_payment({"order_id": order.id, "amount": "1.00"}))

        assert response.status_code == 401
        assert_no_payment_or_order_mutation(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_initialize_payment_rejects_order_owned_by_another_user_without_mutation():
    db = build_session()
    try:
        owner = seed_user(db, "owner@example.com")
        requester = seed_user(db, "requester@example.com")
        product = seed_product(db)
        order = seed_order(db, owner)
        add_payment_ready_item(db, order, product)
        configure_payment_endpoint_test(db, requester)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert_payment_rejection(response, "order_not_found", status_code=404)
        assert_no_payment_or_order_mutation(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_initialize_payment_rejects_unknown_order_like_cross_customer_order():
    db = build_session()
    try:
        user = seed_user(db)
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(post_payment({"order_id": 999999}))

        assert_payment_rejection(response, "order_not_found", status_code=404)
        assert table_count(db, Payment) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_initialize_payment_rejects_non_draft_order_without_mutation():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user, status=OrderStatus.CONFIRMED)
        add_payment_ready_item(db, order, product)
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert_payment_rejection(response, "order_not_payable")
        assert payments_for_order(db, order.id) == []
        assert db.get(Order, order.id).status == OrderStatus.CONFIRMED.value
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "forbidden_field,forged_value",
    [
        ("amount", "1.00"),
        ("currency", "USD"),
        ("payment_status", "verified"),
        ("payment_provider_reference", "pay_forged"),
        ("provider_code", "wompi"),
        ("merchant_reference", "forged-reference"),
        ("provider_checkout_reference", "forged-checkout"),
        ("checkout_expires_at", "2099-01-01T00:00:00Z"),
        ("return_url", "https://attacker.example/return"),
        ("signature", "forged-signature"),
        ("handoff", {"type": "redirect", "url": "https://attacker.example"}),
        ("customer_id", 999),
        ("user_id", 999),
        ("role", "admin"),
        ("is_admin", True),
        ("ownership", "forged-owner"),
    ],
)
def test_initialize_payment_rejects_frontend_payment_claims_without_mutation(
    forbidden_field,
    forged_value,
):
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(
            post_payment({"order_id": order.id, forbidden_field: forged_value})
        )

        assert response.status_code == 422
        assert_no_payment_or_order_mutation(db, order.id)
        assert table_count(db, AuditLog) == 0
        assert table_count(db, PaymentProviderEvent) == 0
        assert table_count(db, PaymentProviderTransaction) == 0
        assert table_count(db, PaymentWebhookEvent) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_initialize_payment_rejects_ineligible_item_snapshot_without_mutation():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product, provider_pricing_reference=None)
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert_payment_rejection(response, "order_items_not_payable")
        assert_no_payment_or_order_mutation(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_initialize_payment_rejects_inactive_product_snapshot_without_mutation():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        product.is_active = False
        db.add(product)
        db.commit()
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert_payment_rejection(response, "order_items_not_payable")
        assert_no_payment_or_order_mutation(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("availability_state", "reason_code"),
    [
        (AvailabilityState.TEMPORARILY_UNAVAILABLE, "temporarily_unavailable"),
        (AvailabilityState.MANUAL_QUOTE_REQUIRED, "manual_quote_required"),
        (AvailabilityState.OUTSOURCED_NOT_MVP_DIRECT, "outsourced_not_mvp_direct"),
    ],
)
def test_initialize_payment_rejects_currently_unavailable_or_manual_quote_items(
    availability_state,
    reason_code,
):
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        configure_payment_endpoint_test(db, user)
        configure_provider_adapter(
            db,
            {
                (CatalogItemType.PRODUCT, product.id): LocalProviderFixture(
                    availability_state=availability_state,
                    provider_cost=Decimal("12.00"),
                    supports_requested_configuration=True,
                    reason_code=reason_code,
                )
            },
        )

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert_payment_rejection(response, reason_code)
        assert_no_payment_or_order_mutation(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("provider_cost", "supports_requested_configuration", "reason_code"),
    [
        (None, True, "provider_cost_missing"),
        (Decimal("12.00"), False, "configuration_not_supported"),
    ],
)
def test_initialize_payment_rejects_currently_non_priceable_items(
    provider_cost,
    supports_requested_configuration,
    reason_code,
):
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        configure_payment_endpoint_test(db, user)
        configure_provider_adapter(
            db,
            {
                (CatalogItemType.PRODUCT, product.id): LocalProviderFixture(
                    availability_state=AvailabilityState.AVAILABLE,
                    provider_cost=provider_cost,
                    supports_requested_configuration=supports_requested_configuration,
                    reason_code=reason_code,
                )
            },
        )

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert_payment_rejection(response, reason_code)
        assert_no_payment_or_order_mutation(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "existing_status",
    [
        PaymentStatus.INITIATED,
        PaymentStatus.PENDING,
        PaymentStatus.REQUIRES_ACTION,
    ],
)
def test_initialize_payment_rejects_active_legacy_payment_without_duplicate(
    existing_status,
):
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        seed_payment(db, order, status=existing_status)
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert_payment_rejection(
            response,
            "payment_provider_not_routable",
            status_code=409,
        )
        assert table_count(db, Payment) == 1
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.DRAFT.value
        assert stored_order.payment_provider_reference is None
        assert stored_order.payment_verified_at is None
        assert stored_order.provider_handoff_reference is None
        assert stored_order.provider_handoff_sent_at is None
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_initialize_payment_allows_new_attempt_after_terminal_payment():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        failed_payment = seed_payment(db, order, status=PaymentStatus.FAILED)
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert response.status_code == 201
        payload = response.json()["data"]
        assert payload["payment_id"] != failed_payment.id
        assert payload["payment_status"] == PaymentStatus.REQUIRES_ACTION.value
        payments = payments_for_order(db, order.id)
        assert [payment.status for payment in payments] == [
            PaymentStatus.FAILED.value,
            PaymentStatus.REQUIRES_ACTION.value,
        ]
        assert payments[1].provider_code == "wompi"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_initialize_payment_reuses_unexpired_wompi_requires_action_handoff():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        expiration = datetime.now(UTC) + timedelta(minutes=20)
        existing_payment = seed_payment(
            db,
            order,
            status=PaymentStatus.REQUIRES_ACTION,
            provider_code="wompi",
            checkout_expires_at=expiration,
        )
        configure_payment_endpoint_test(db, user)

        first_response = asyncio.run(post_payment({"order_id": order.id}))
        second_response = asyncio.run(post_payment({"order_id": order.id}))

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert first_response.json() == second_response.json()
        payload = first_response.json()["data"]
        assert payload["payment_id"] == existing_payment.id
        assert payload["payment_status"] == PaymentStatus.REQUIRES_ACTION.value
        assert table_count(db, Payment) == 1
        stored_expiration = db.get(Payment, existing_payment.id).checkout_expires_at
        assert stored_expiration.replace(tzinfo=UTC) == expiration
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("payment_status", "expired", "expected_code"),
    [
        (PaymentStatus.INITIATED, False, "payment_state_invalid"),
        (PaymentStatus.PENDING, False, "payment_in_progress"),
        (PaymentStatus.PENDING, True, "payment_in_progress"),
    ],
)
def test_initialize_payment_rejects_non_restartable_wompi_state_without_mutation(
    payment_status,
    expired,
    expected_code,
):
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        expiration_delta = timedelta(minutes=-1 if expired else 20)
        payment = seed_payment(
            db,
            order,
            status=payment_status,
            provider_code="wompi",
            checkout_expires_at=datetime.now(UTC) + expiration_delta,
        )
        configure_payment_endpoint_test(db, user)
        original_expiration = payment.checkout_expires_at

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert_payment_rejection(response, expected_code, status_code=409)
        stored_payment = db.get(Payment, payment.id)
        assert stored_payment.status == payment_status.value
        assert stored_payment.checkout_expires_at == original_expiration
        assert table_count(db, Payment) == 1
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "payment_status",
    [PaymentStatus.INITIATED, PaymentStatus.REQUIRES_ACTION],
)
def test_initialize_payment_replaces_expired_restartable_wompi_payment(
    payment_status,
):
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        expired_payment = seed_payment(
            db,
            order,
            status=payment_status,
            provider_code="wompi",
            checkout_expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert response.status_code == 201
        payments = payments_for_order(db, order.id)
        assert len(payments) == 2
        assert payments[0].id == expired_payment.id
        assert payments[0].status == PaymentStatus.EXPIRED.value
        assert payments[1].status == PaymentStatus.REQUIRES_ACTION.value
        assert payments[1].merchant_reference == f"placamia-payment-{payments[1].id}"
        assert response.json()["data"]["payment_id"] == payments[1].id
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "payment_status",
    [
        PaymentStatus.EXPIRED,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
    ],
)
def test_initialize_payment_preserves_terminal_history_and_creates_wompi_payment(
    payment_status,
):
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        historical_payment = seed_payment(db, order, status=payment_status)
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert response.status_code == 201
        assert db.get(Payment, historical_payment.id).status == payment_status.value
        assert len(payments_for_order(db, order.id)) == 2
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_initialize_payment_rejects_verified_history_without_new_payment():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        verified_payment = seed_payment(
            db,
            order,
            status=PaymentStatus.VERIFIED,
            provider_code="wompi",
        )
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert_payment_rejection(response, "order_not_payable")
        assert payments_for_order(db, order.id) == [verified_payment]
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize("provider_code", ["legacy_generic", "unknown_provider"])
def test_initialize_payment_rejects_non_routable_active_provider_before_config(
    provider_code,
):
    class FailIfCreated:
        def create(self):
            raise AssertionError("Provider configuration must not be evaluated")

    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        payment = seed_payment(
            db,
            order,
            status=PaymentStatus.REQUIRES_ACTION,
            provider_code=provider_code,
            checkout_expires_at=datetime.now(UTC) + timedelta(minutes=20),
        )
        configure_payment_endpoint_test(db, user)
        configure_payment_runtime_factory(FailIfCreated())

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert_payment_rejection(
            response,
            "payment_provider_not_routable",
            status_code=409,
        )
        assert payments_for_order(db, order.id) == [payment]
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_initialize_payment_owner_lookup_precedes_provider_configuration():
    class FailIfCreated:
        def create(self):
            raise AssertionError("Provider configuration must not be evaluated")

    db = build_session()
    try:
        owner = seed_user(db, "owner@example.com")
        requester = seed_user(db, "requester@example.com")
        product = seed_product(db)
        order = seed_order(db, owner)
        add_payment_ready_item(db, order, product)
        configure_payment_endpoint_test(db, requester)
        configure_payment_runtime_factory(FailIfCreated())

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert_payment_rejection(response, "order_not_found", status_code=404)
        assert_no_payment_or_order_mutation(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ENV", None),
        ("PAYMENT_PROVIDER_DEFAULT", None),
        ("PAYMENT_RETURN_URL", None),
        ("PAYMENT_CHECKOUT_TTL_SECONDS", "60"),
        ("WOMPI_ENVIRONMENT", "production"),
        ("WOMPI_PUBLIC_KEY", None),
        ("WOMPI_INTEGRITY_SECRET", None),
    ],
)
def test_initialize_payment_returns_redacted_503_for_invalid_configuration(
    field,
    value,
):
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        configure_payment_endpoint_test(db, user)
        invalid_settings = ValidPaymentSettings()
        setattr(invalid_settings, field, value)
        configure_payment_runtime_factory(
            ConfiguredPaymentProviderRuntimeFactory(invalid_settings)
        )

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert response.status_code == 503
        assert response.json() == {
            "detail": {
                "code": "payment_provider_unavailable",
                "message": "Payment provider is temporarily unavailable.",
            }
        }
        assert_no_payment_or_order_mutation(db, order.id)
        assert "integrity" not in response.text.lower()
        assert "public" not in response.text.lower()
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_initialize_payment_existing_wompi_ignores_current_default_provider():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        payment = seed_payment(
            db,
            order,
            status=PaymentStatus.REQUIRES_ACTION,
            provider_code="wompi",
            checkout_expires_at=datetime.now(UTC) + timedelta(minutes=20),
        )
        configure_payment_endpoint_test(db, user)
        settings = ValidPaymentSettings()
        settings.PAYMENT_PROVIDER_DEFAULT = "future_provider"
        configure_payment_runtime_factory(
            ConfiguredPaymentProviderRuntimeFactory(settings)
        )

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert response.status_code == 200
        assert response.json()["data"]["payment_id"] == payment.id
        assert table_count(db, Payment) == 1
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("currency", "total_amount", "expected_code"),
    [
        ("USD", "40.00", "unsupported_payment_currency"),
        ("COP", "0.00", "invalid_payment_amount"),
    ],
)
def test_initialize_payment_rejects_unsupported_currency_or_invalid_amount(
    currency,
    total_amount,
    expected_code,
):
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(
            db,
            user,
            currency=currency,
            total_amount=total_amount,
        )
        add_payment_ready_item(db, order, product, total_amount=total_amount)
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert_payment_rejection(response, expected_code)
        assert_no_payment_or_order_mutation(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("missing_field", "missing_value"),
    [("merchant_reference", ""), ("checkout_expires_at", None)],
)
def test_initialize_payment_rejects_incomplete_wompi_identity_without_mutation(
    missing_field,
    missing_value,
):
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        payment = seed_payment(
            db,
            order,
            status=PaymentStatus.REQUIRES_ACTION,
            provider_code="wompi",
            checkout_expires_at=datetime.now(UTC) + timedelta(minutes=20),
        )
        setattr(payment, missing_field, missing_value)
        db.commit()
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert_payment_rejection(response, "payment_state_invalid", status_code=409)
        assert table_count(db, Payment) == 1
        assert db.get(Payment, payment.id).status == PaymentStatus.REQUIRES_ACTION.value
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_payment_initialization_openapi_documents_wompi_handoff_contract():
    async def get_openapi_schema():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/openapi.json")

    schema = asyncio.run(get_openapi_schema()).json()
    operation = schema["paths"]["/api/v1/payments"]["post"]

    assert operation["summary"] == "Initialize payment"
    assert operation["security"] == [{"HTTPBearer": []}]
    assert {"200", "201", "400", "401", "404", "409", "422", "503"} <= set(
        operation["responses"]
    )
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PaymentInitializationRequest"
    }
    data_properties = schema["components"]["schemas"]["PaymentInitializationData"][
        "properties"
    ]
    assert set(data_properties) == {
        "payment_id",
        "order_id",
        "payment_status",
        "amount",
        "currency",
        "handoff",
        "checkout_expires_at",
    }
    assert data_properties["handoff"] == {
        "$ref": "#/components/schemas/PaymentRedirectHandoff"
    }


def test_handoff_construction_failure_rolls_back_allocated_payment():
    class FailingProvider:
        async def initialize_checkout(self, request):
            raise RuntimeError("sensitive provider diagnostic")

    class FailingRuntimeFactory:
        def create(self):
            return PaymentProviderRuntime(
                registry=PaymentProviderRegistry(
                    {"wompi": FailingProvider()},
                    "wompi",
                ),
                return_url="http://localhost:3000/payments/return",
                checkout_ttl_seconds=1800,
            )

    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        configure_payment_endpoint_test(db, user)
        configure_payment_runtime_factory(FailingRuntimeFactory())

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert response.status_code == 503
        assert response.json()["detail"] == {
            "code": "payment_provider_unavailable",
            "message": "Payment provider is temporarily unavailable.",
        }
        assert "sensitive provider diagnostic" not in response.text
        assert_no_payment_or_order_mutation(db, order.id)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_replacement_failure_rolls_back_expiration_transition():
    class FailingRuntimeFactory:
        def create(self):
            raise RuntimeError("configuration failed")

    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        stale_payment = seed_payment(
            db,
            order,
            status=PaymentStatus.REQUIRES_ACTION,
            provider_code="wompi",
            checkout_expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        configure_payment_endpoint_test(db, user)
        configure_payment_runtime_factory(FailingRuntimeFactory())

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert response.status_code == 503
        assert table_count(db, Payment) == 1
        assert (
            db.get(Payment, stale_payment.id).status
            == PaymentStatus.REQUIRES_ACTION.value
        )
    finally:
        app.dependency_overrides.clear()
        db.close()
