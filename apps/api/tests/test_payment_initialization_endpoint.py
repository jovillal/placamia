import asyncio
from decimal import Decimal

import httpx
import pytest
from app.api.dependencies import get_current_user, get_provider_adapter
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
from app.models.category import Category
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.user import User
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
) -> Payment:
    """Persist one Payment for initialization idempotency tests."""
    payment = Payment(
        order_id=order.id,
        status=status.value,
        amount=Decimal(amount),
        currency=order.currency,
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


def configure_provider_adapter(db, fixtures) -> None:
    """Override the provider adapter with test-controlled fixtures."""

    async def override_get_provider_adapter():
        return LocalMockProviderAdapter(fixtures)

    app.dependency_overrides[get_provider_adapter] = override_get_provider_adapter


async def post_payment(payload: dict[str, object]):
    """Call the payment initialization endpoint through ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post("/api/v1/payments", json=payload)


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


def test_initialize_payment_creates_initiated_payment_from_backend_order_state():
    db = build_session()
    try:
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
        assert payload["payment_status"] == PaymentStatus.INITIATED.value
        assert payload["amount"] == "40.00"
        assert payload["currency"] == "COP"

        payments = payments_for_order(db, order.id)
        assert len(payments) == 1
        assert payments[0].status == PaymentStatus.INITIATED.value
        assert payments[0].amount == Decimal("40.00")
        assert payments[0].currency == "COP"
        assert payments[0].payment_provider_reference is None
        assert payments[0].verified_at is None

        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.DRAFT.value
        assert stored_order.payment_provider_reference is None
        assert stored_order.payment_verified_at is None
        assert stored_order.provider_handoff_reference is None
        assert stored_order.provider_handoff_sent_at is None
    finally:
        app.dependency_overrides.clear()
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
        ("customer_id", 999),
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
def test_initialize_payment_returns_existing_non_terminal_attempt_without_duplicate(
    existing_status,
):
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        order = seed_order(db, user)
        add_payment_ready_item(db, order, product)
        existing_payment = seed_payment(db, order, status=existing_status)
        configure_payment_endpoint_test(db, user)

        response = asyncio.run(post_payment({"order_id": order.id}))

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["payment_id"] == existing_payment.id
        assert payload["payment_status"] == existing_status.value
        assert table_count(db, Payment) == 1
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
        assert payload["payment_status"] == PaymentStatus.INITIATED.value
        payments = payments_for_order(db, order.id)
        assert [payment.status for payment in payments] == [
            PaymentStatus.FAILED.value,
            PaymentStatus.INITIATED.value,
        ]
    finally:
        app.dependency_overrides.clear()
        db.close()
