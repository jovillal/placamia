import asyncio
from decimal import Decimal

import httpx
import pytest
from app.api.dependencies import get_provider_adapter
from app.core.database import Base, get_db
from app.domain.provider_adapter import (
    AvailabilityState,
    CatalogItemType,
    LocalMockProviderAdapter,
    LocalProviderFixture,
)
from app.main import app
from app.models.category import Category
from app.models.design import Design
from app.models.kit import Kit
from app.models.kit_item import KitItem
from app.models.product import Product
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for pricing endpoint tests."""
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


async def post_pricing_quote(payload: dict[str, object]):
    """Call the pricing quote endpoint through the ASGI test transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post("/api/v1/pricing/quotes", json=payload)


def available_fixture(cost: str = "12.00") -> LocalProviderFixture:
    """Return a direct-checkout eligible local provider fixture."""
    return LocalProviderFixture(
        availability_state=AvailabilityState.AVAILABLE,
        provider_cost=Decimal(cost),
        supports_requested_configuration=True,
    )


def seed_product(
    db,
    base_price: str = "20.00",
    is_active: bool = True,
) -> Product:
    """Persist one Product for pricing endpoint tests."""
    category = Category(name="Emergency", description=None)
    product = Product(
        name="Emergency exit sign",
        description=None,
        category=category,
        base_price=Decimal(base_price),
        is_active=is_active,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def seed_kit(db, products: list[tuple[Product, int]]) -> Kit:
    """Persist one Kit with the supplied fixed backend-owned contents."""
    kit = Kit(
        name="Emergency evacuation kit",
        description=None,
        is_active=True,
    )
    db.add(kit)
    db.flush()
    db.add_all(
        [
            KitItem(
                kit=kit,
                product=product,
                quantity=quantity,
            )
            for product, quantity in products
        ]
    )
    db.commit()
    db.refresh(kit)
    return kit


def persistence_snapshot(db) -> dict[str, list[tuple[object, ...]]]:
    """Return pricing-related persisted state for read-only assertions."""
    return {
        "products": db.execute(select(Product.__table__).order_by(Product.id)).all(),
        "kits": db.execute(select(Kit.__table__).order_by(Kit.id)).all(),
        "kit_items": db.execute(select(KitItem.__table__).order_by(KitItem.id)).all(),
        "designs": db.execute(select(Design.__table__).order_by(Design.id)).all(),
    }


def table_count(db, model) -> int:
    """Return the number of persisted rows for a model."""
    return db.scalar(select(func.count()).select_from(model))


def configure_pricing_endpoint_test(db, fixtures):
    """Install FastAPI dependency overrides for one pricing endpoint test."""
    configure_pricing_endpoint_test_with_adapter(
        db,
        LocalMockProviderAdapter(fixtures),
    )


def configure_pricing_endpoint_test_with_adapter(db, provider_adapter):
    """Install FastAPI overrides with a caller-owned provider adapter."""

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_provider_adapter():
        return provider_adapter

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = override_provider_adapter


def assert_pricing_rejection(response, code: str) -> None:
    """Assert an API response contains a stable pricing rejection code."""
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == code


def test_pricing_quote_endpoint_returns_product_preview_without_provider_cost():
    db = build_session()
    product = seed_product(db, base_price="20.00")
    configure_pricing_endpoint_test(
        db,
        {(CatalogItemType.PRODUCT, product.id): available_fixture("12.00")},
    )

    try:
        response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "product",
                    "item_id": product.id,
                    "quantity": 3,
                }
            )
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload == {
            "item_type": "product",
            "item_id": product.id,
            "quantity": 3,
            "currency": "COP",
            "customer_unit_price": "20.00",
            "customer_subtotal": "60.00",
            "preview_total": "60.00",
            "pricing_rule": "temporary_product_base_price_v1",
            "provider_quote_reference": f"local-quote-product-{product.id}",
        }
        assert "provider_cost" not in payload
        assert "provider_cost_input" not in payload
        assert "provider_cost_total" not in payload
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_pricing_quote_endpoint_does_not_trigger_provider_handoff():
    db = build_session()
    product = seed_product(db, base_price="20.00")
    provider_adapter = LocalMockProviderAdapter(
        {(CatalogItemType.PRODUCT, product.id): available_fixture("12.00")}
    )
    configure_pricing_endpoint_test_with_adapter(db, provider_adapter)

    try:
        response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "product",
                    "item_id": product.id,
                    "quantity": 1,
                }
            )
        )

        assert response.status_code == 200
        assert provider_adapter.handoffs_by_key == {}
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_pricing_quote_endpoint_returns_exact_read_only_kit_preview():
    db = build_session()
    first_product = seed_product(db, base_price="20.00")
    second_product = Product(
        name="Assembly point sign",
        description=None,
        category_id=first_product.category_id,
        base_price=Decimal("10.00"),
        is_active=True,
    )
    db.add(second_product)
    db.commit()
    db.refresh(second_product)
    kit = seed_kit(db, [(first_product, 2), (second_product, 1)])
    provider_adapter = LocalMockProviderAdapter(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("30.00"),
            (CatalogItemType.PRODUCT, first_product.id): available_fixture("12.00"),
            (CatalogItemType.PRODUCT, second_product.id): available_fixture("6.00"),
        }
    )
    configure_pricing_endpoint_test_with_adapter(db, provider_adapter)
    persistence_before = persistence_snapshot(db)

    try:
        response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "kit",
                    "item_id": kit.id,
                    "quantity": 3,
                }
            )
        )

        assert response.status_code == 200
        assert response.json() == {
            "item_type": "kit",
            "item_id": kit.id,
            "quantity": 3,
            "currency": "COP",
            "customer_unit_price": "50.00",
            "customer_subtotal": "150.00",
            "preview_total": "150.00",
            "pricing_rule": "temporary_kit_contents_base_price_v1",
            "provider_quote_reference": f"local-quote-kit-{kit.id}",
            "lines": [
                {
                    "product_id": first_product.id,
                    "product_name": "Emergency exit sign",
                    "quantity_per_kit": 2,
                    "total_quantity": 6,
                    "customer_unit_price": "20.00",
                    "customer_subtotal": "120.00",
                },
                {
                    "product_id": second_product.id,
                    "product_name": "Assembly point sign",
                    "quantity_per_kit": 1,
                    "total_quantity": 3,
                    "customer_unit_price": "10.00",
                    "customer_subtotal": "30.00",
                },
            ],
        }
        assert persistence_snapshot(db) == persistence_before
        assert provider_adapter.handoffs_by_key == {}
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_pricing_quote_endpoint_returns_customer_safe_kit_not_found():
    db = build_session()
    configure_pricing_endpoint_test(db, {})
    persistence_before = persistence_snapshot(db)

    try:
        response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "kit",
                    "item_id": 999,
                    "quantity": 1,
                }
            )
        )

        assert response.status_code == 404
        assert response.json() == {
            "detail": {"code": "kit_not_found", "message": "Kit not found."}
        }
        assert persistence_snapshot(db) == persistence_before
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "extra_claim",
    [
        {"arbitrary": "value"},
        {"customer_id": 999},
        {"provider_cost": "0.01"},
    ],
)
def test_pricing_quote_endpoint_rejects_all_kit_extras_without_mutation(
    extra_claim,
):
    db = build_session()
    product = seed_product(db)
    kit = seed_kit(db, [(product, 1)])
    configure_pricing_endpoint_test(db, {})
    persistence_before = persistence_snapshot(db)

    try:
        response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "kit",
                    "item_id": kit.id,
                    "quantity": 1,
                    **extra_claim,
                }
            )
        )

        assert_pricing_rejection(response, "frontend_pricing_claim_not_allowed")
        assert persistence_snapshot(db) == persistence_before
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("quantity", 0, "quantity_too_low"),
        ("quantity", -1, "quantity_too_low"),
        ("quantity", 101, "quantity_too_high"),
        ("quantity", 1.5, "invalid_quantity"),
        ("quantity", True, "invalid_quantity"),
        ("options", {"material": "forged"}, "invalid_configuration"),
        ("options", [], "invalid_configuration"),
        ("options", None, "invalid_configuration"),
    ],
)
def test_pricing_quote_endpoint_returns_kit_business_rejections(
    field,
    value,
    code,
):
    db = build_session()
    product = seed_product(db)
    kit = seed_kit(db, [(product, 1)])
    configure_pricing_endpoint_test(db, {})
    persistence_before = persistence_snapshot(db)
    payload = {
        "item_type": "kit",
        "item_id": kit.id,
        "quantity": 1,
        field: value,
    }

    try:
        response = asyncio.run(post_pricing_quote(payload))

        assert_pricing_rejection(response, code)
        assert persistence_snapshot(db) == persistence_before
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_pricing_quote_endpoint_hides_inactive_required_kit_content():
    db = build_session()
    product = seed_product(db, is_active=False)
    kit = seed_kit(db, [(product, 1)])
    configure_pricing_endpoint_test(db, {})
    persistence_before = persistence_snapshot(db)

    try:
        response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "kit",
                    "item_id": kit.id,
                    "quantity": 1,
                }
            )
        )

        assert response.status_code == 400
        assert response.json() == {
            "detail": {
                "code": "kit_contents_unavailable",
                "message": "Kit is not eligible for direct checkout pricing.",
            }
        }
        assert persistence_snapshot(db) == persistence_before
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_pricing_quote_endpoint_rejects_design_pricing_as_deferred():
    db = build_session()
    configure_pricing_endpoint_test(db, {})

    try:
        response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "design",
                    "item_id": 1,
                    "quantity": 1,
                }
            )
        )

        assert_pricing_rejection(response, "design_pricing_contract_only")
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "frontend_claim",
    [
        {"price": "0.01"},
        {"provider_cost": "0.01"},
        {"provider_id": "forged-provider"},
        {"user_id": 999},
        {"role": "admin"},
        {"is_admin": True},
        {"availability_state": "available"},
        {"direct_checkout_eligible": True},
    ],
)
def test_pricing_quote_endpoint_rejects_frontend_tampering_without_mutation(
    frontend_claim,
):
    db = build_session()
    product = seed_product(db, base_price="20.00")
    initial_product_count = table_count(db, Product)
    initial_design_count = table_count(db, Design)
    configure_pricing_endpoint_test(
        db,
        {(CatalogItemType.PRODUCT, product.id): available_fixture("12.00")},
    )

    try:
        response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "product",
                    "item_id": product.id,
                    "quantity": 1,
                    **frontend_claim,
                }
            )
        )

        assert_pricing_rejection(response, "frontend_pricing_claim_not_allowed")
        assert table_count(db, Product) == initial_product_count
        assert table_count(db, Design) == initial_design_count
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_pricing_quote_endpoint_rejects_inactive_product_without_mutation():
    db = build_session()
    product = seed_product(db, is_active=False)
    initial_product_count = table_count(db, Product)
    initial_design_count = table_count(db, Design)
    configure_pricing_endpoint_test(
        db,
        {(CatalogItemType.PRODUCT, product.id): available_fixture("12.00")},
    )

    try:
        response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "product",
                    "item_id": product.id,
                    "quantity": 1,
                }
            )
        )

        assert_pricing_rejection(response, "inactive")
        assert table_count(db, Product) == initial_product_count
        assert table_count(db, Design) == initial_design_count
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_pricing_quote_endpoint_rejects_invalid_options_and_quantity():
    db = build_session()
    product = seed_product(db)
    configure_pricing_endpoint_test(
        db,
        {(CatalogItemType.PRODUCT, product.id): available_fixture("12.00")},
    )

    try:
        invalid_option_response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "product",
                    "item_id": product.id,
                    "quantity": 1,
                    "options": {"material": "forged-acrylic"},
                }
            )
        )
        invalid_quantity_response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "product",
                    "item_id": product.id,
                    "quantity": 0,
                }
            )
        )

        assert_pricing_rejection(invalid_option_response, "invalid_configuration")
        assert_pricing_rejection(invalid_quantity_response, "quantity_too_low")
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
def test_pricing_quote_endpoint_rejects_ineligible_provider_states(
    availability_state,
    reason_code,
):
    db = build_session()
    product = seed_product(db)
    configure_pricing_endpoint_test(
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

    try:
        response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "product",
                    "item_id": product.id,
                    "quantity": 1,
                }
            )
        )

        assert_pricing_rejection(response, reason_code)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_pricing_quote_endpoint_is_documented_in_openapi():
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
    operation = schema["paths"]["/api/v1/pricing/quotes"]["post"]
    assert operation["summary"] == "Preview Path A pricing"
    success_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert success_schema["discriminator"]["propertyName"] == "item_type"
    assert success_schema["discriminator"]["mapping"] == {
        "product": "#/components/schemas/ProductPricingQuoteResponse",
        "kit": "#/components/schemas/KitPricingQuoteResponse",
    }
    product_properties = schema["components"]["schemas"]["ProductPricingQuoteResponse"][
        "properties"
    ]
    kit_properties = schema["components"]["schemas"]["KitPricingQuoteResponse"][
        "properties"
    ]
    assert "lines" not in product_properties
    assert kit_properties["lines"]["items"] == {
        "$ref": "#/components/schemas/KitPricingLineResponse"
    }
