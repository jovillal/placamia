import asyncio
from decimal import Decimal

import httpx
import pytest
from app.api.dependencies import get_current_user, get_provider_adapter
from app.core.database import Base, get_db
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
from app.models.product import Product
from app.models.user import User
from app.services.checkout_service import DEFAULT_TERMS_POLICY_VERSION
from app.services.pricing_service import PricingItemType
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for order endpoint tests."""
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
    """Persist one active user for authenticated order endpoint tests."""
    user = User(email=email, full_name="Test Buyer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_product(
    db,
    *,
    name: str = "Emergency exit sign",
    base_price: str = "20.00",
    is_active: bool = True,
) -> Product:
    """Persist one Product for draft order creation tests."""
    category = Category(name="Emergency", description=None)
    product = Product(
        name=name,
        description="Catalog description",
        category=category,
        base_price=Decimal(base_price),
        is_active=is_active,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def available_fixture(cost: str = "12.00") -> LocalProviderFixture:
    """Return a direct-checkout eligible local provider fixture."""
    return LocalProviderFixture(
        availability_state=AvailabilityState.AVAILABLE,
        provider_cost=Decimal(cost),
        supports_requested_configuration=True,
    )


def unavailable_fixture(reason_code: str) -> LocalProviderFixture:
    """Return a local provider fixture that blocks direct checkout."""
    return LocalProviderFixture(
        availability_state=AvailabilityState.MANUAL_QUOTE_REQUIRED,
        provider_cost=Decimal("12.00"),
        supports_requested_configuration=True,
        reason_code=reason_code,
    )


def order_payload(product: Product, **overrides) -> dict[str, object]:
    """Build a direct-checkout order creation payload."""
    payload: dict[str, object] = {
        "item_type": PricingItemType.PRODUCT.value,
        "item_id": product.id,
        "quantity": 2,
        "terms_acknowledgement": {
            "accepted": True,
            "policy_version": DEFAULT_TERMS_POLICY_VERSION,
        },
    }
    payload.update(overrides)
    return payload


async def post_order(payload: dict[str, object]):
    """Call the draft order creation endpoint through ASGI test transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post("/api/v1/orders", json=payload)


def configure_order_endpoint_test(db, current_user, provider_adapter) -> None:
    """Install FastAPI overrides for an authenticated order endpoint test."""

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_get_current_user():
        return current_user

    async def override_provider_adapter():
        return provider_adapter

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_provider_adapter] = override_provider_adapter


def configure_unauthenticated_order_endpoint_test(db, provider_adapter) -> None:
    """Install FastAPI overrides while leaving authentication enforced."""

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_provider_adapter():
        return provider_adapter

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = override_provider_adapter


def table_count(db, model) -> int:
    """Return the number of persisted rows for a model."""
    return db.scalar(select(func.count()).select_from(model))


def assert_order_rejection(response, code: str) -> None:
    """Assert an API response contains a stable order rejection code."""
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == code


def assert_no_order_mutation(db, provider_adapter) -> None:
    """Assert rejected order creation did not create order or provider records."""
    assert table_count(db, Order) == 0
    assert table_count(db, OrderItem) == 0
    assert provider_adapter.handoffs_by_key == {}


def test_create_order_endpoint_persists_draft_order_from_validated_checkout_state():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db, base_price="20.00")
        provider_adapter = LocalMockProviderAdapter(
            {(CatalogItemType.PRODUCT, product.id): available_fixture("12.00")}
        )
        configure_order_endpoint_test(db, user, provider_adapter)

        response = asyncio.run(post_order(order_payload(product, quantity=3)))

        assert response.status_code == 201
        payload = response.json()
        assert payload["id"] == 1
        assert payload["customer_id"] == user.id
        assert payload["status"] == "draft"
        assert payload["subtotal_amount"] == "60.00"
        assert payload["discount_amount"] == "0.00"
        assert payload["tax_amount"] == "0.00"
        assert payload["total_amount"] == "60.00"
        assert payload["currency"] == "COP"
        assert payload["assigned_provider_id"] == "local-provider"
        assert payload["terms_policy_version"] == DEFAULT_TERMS_POLICY_VERSION
        assert payload["payment_provider_reference"] is None
        assert payload["payment_verified_at"] is None
        assert payload["provider_handoff_reference"] is None
        assert payload["provider_handoff_sent_at"] is None

        assert len(payload["items"]) == 1
        item_payload = payload["items"][0]
        assert item_payload["item_type"] == "product"
        assert item_payload["product_id"] == product.id
        assert item_payload["display_name"] == product.name
        assert item_payload["customer_safe_description"] == product.description
        assert item_payload["selected_options"] == {}
        assert item_payload["quantity"] == 3
        assert item_payload["unit_price_amount"] == "20.00"
        assert item_payload["line_subtotal_amount"] == "60.00"
        assert item_payload["line_discount_amount"] == "0.00"
        assert item_payload["line_tax_amount"] == "0.00"
        assert item_payload["line_total_amount"] == "60.00"
        assert item_payload["currency"] == "COP"
        assert item_payload["assigned_provider_id"] == "local-provider"
        assert item_payload["provider_pricing_reference"] == (
            f"local-quote-product-{product.id}"
        )
        assert "provider_cost" not in item_payload
        assert table_count(db, Order) == 1
        assert table_count(db, OrderItem) == 1
        assert provider_adapter.handoffs_by_key == {}
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_create_order_endpoint_rejects_unauthenticated_access_without_mutation():
    db = build_session()
    try:
        product = seed_product(db)
        provider_adapter = LocalMockProviderAdapter(
            {(CatalogItemType.PRODUCT, product.id): available_fixture()}
        )
        configure_unauthenticated_order_endpoint_test(db, provider_adapter)

        response = asyncio.run(post_order(order_payload(product)))

        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid authentication credentials"}
        assert_no_order_mutation(db, provider_adapter)
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "frontend_claim",
    [
        {"customer_id": 999},
        {"id": 999},
        {"user_id": 999},
        {"owner_id": 999},
        {"created_at": "2026-06-08T00:00:00Z"},
        {"updated_at": "2026-06-08T00:00:00Z"},
        {"role": "admin"},
        {"is_admin": True},
        {"status": "confirmed"},
        {"items": []},
        {"payment_provider_reference": "pay_forged"},
        {"payment_verified_at": "2026-06-08T00:00:00Z"},
        {"provider_handoff_reference": "handoff_forged"},
        {"provider_handoff_sent_at": "2026-06-08T00:00:00Z"},
        {"subtotal_amount": "0.01"},
        {"total_amount": "0.01"},
        {"provider_cost": "0.01"},
        {"assigned_provider_id": "forged-provider"},
        {"terms_policy_version": DEFAULT_TERMS_POLICY_VERSION},
    ],
)
def test_create_order_endpoint_rejects_frontend_security_claims_without_mutation(
    frontend_claim,
):
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        provider_adapter = LocalMockProviderAdapter(
            {(CatalogItemType.PRODUCT, product.id): available_fixture()}
        )
        configure_order_endpoint_test(db, user, provider_adapter)

        response = asyncio.run(post_order(order_payload(product, **frontend_claim)))

        assert_order_rejection(response, "frontend_order_claim_not_allowed")
        assert_no_order_mutation(db, provider_adapter)
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("payload_overrides", "code"),
    [
        ({"terms_acknowledgement": None}, "terms_acknowledgement_required"),
        (
            {
                "terms_acknowledgement": {
                    "accepted": True,
                    "policy_version": "forged-v0",
                }
            },
            "terms_policy_version_mismatch",
        ),
        ({"options": {"finish": "forged"}}, "invalid_configuration"),
    ],
)
def test_create_order_endpoint_rejects_invalid_checkout_without_mutation(
    payload_overrides,
    code,
):
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        provider_adapter = LocalMockProviderAdapter(
            {(CatalogItemType.PRODUCT, product.id): available_fixture()}
        )
        configure_order_endpoint_test(db, user, provider_adapter)

        response = asyncio.run(post_order(order_payload(product, **payload_overrides)))

        assert_order_rejection(response, code)
        assert_no_order_mutation(db, provider_adapter)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_create_order_endpoint_rejects_ineligible_provider_state_without_mutation():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        provider_adapter = LocalMockProviderAdapter(
            {
                (CatalogItemType.PRODUCT, product.id): unavailable_fixture(
                    "manual_quote_required"
                )
            }
        )
        configure_order_endpoint_test(db, user, provider_adapter)

        response = asyncio.run(post_order(order_payload(product)))

        assert_order_rejection(response, "manual_quote_required")
        assert_no_order_mutation(db, provider_adapter)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_created_order_item_snapshot_survives_later_product_changes():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db, name="Original product name")
        provider_adapter = LocalMockProviderAdapter(
            {(CatalogItemType.PRODUCT, product.id): available_fixture()}
        )
        configure_order_endpoint_test(db, user, provider_adapter)

        response = asyncio.run(post_order(order_payload(product)))
        assert response.status_code == 201
        item_id = response.json()["items"][0]["id"]

        product.name = "Updated product name"
        product.description = "Updated description"
        db.commit()

        stored_item = db.get(OrderItem, item_id)
        assert stored_item is not None
        assert stored_item.display_name == "Original product name"
        assert stored_item.customer_safe_description == "Catalog description"
        assert stored_item.product.name == "Updated product name"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_create_order_endpoint_is_documented_in_openapi():
    async def get_openapi_schema():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/openapi.json")

    response = asyncio.run(get_openapi_schema())

    assert response.status_code == 200
    schema = response.json()
    operation = schema["paths"]["/api/v1/orders"]["post"]
    assert operation["summary"] == "Create draft order"
    assert "201" in operation["responses"]
