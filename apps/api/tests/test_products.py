import asyncio
from datetime import UTC, datetime
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
from app.models.product import Product
from app.repositories.product_repository import ProductRepository
from app.services.product_service import ProductService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
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


def seed_category(db, name: str = "Warning") -> Category:
    """Persist one catalog Category for product endpoint tests."""
    category = Category(name=name, description=None)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def seed_product(
    db,
    category: Category,
    *,
    name: str,
    is_active: bool = True,
    base_price: str = "20.00",
) -> Product:
    """Persist one Product for public catalog endpoint tests."""
    product = Product(
        name=name,
        description=f"{name} description",
        category=category,
        base_price=Decimal(base_price),
        is_active=is_active,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def available_product_fixture() -> LocalProviderFixture:
    """Return a direct-checkout eligible local provider fixture."""
    return LocalProviderFixture(
        availability_state=AvailabilityState.AVAILABLE,
        provider_cost=Decimal("12.50"),
        supports_requested_configuration=True,
    )


def configure_product_endpoint_test(db, fixtures=None) -> None:
    """Install dependency overrides for public product endpoint tests."""

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    if fixtures is None:
        fixtures = {
            (CatalogItemType.PRODUCT, product.id): available_product_fixture()
            for product in db.query(Product).all()
        }

    async def override_provider_adapter():
        return LocalMockProviderAdapter(fixtures)

    app.dependency_overrides[get_provider_adapter] = override_provider_adapter


async def request_product_list(params=None):
    """Call the public product list endpoint through ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get("/api/v1/catalog/products", params=params)


def test_product_model_links_to_category():
    db = build_session()
    try:
        category = Category(name="Warning", description="Warning signs")
        product = Product(
            name="Caution floor sign",
            description="Rigid caution sign",
            category=category,
            base_price=Decimal("19.99"),
        )
        db.add(product)
        db.commit()
        db.refresh(category)
        db.refresh(product)

        assert product.category.name == "Warning"
        assert category.products == [product]
        assert product.is_active is True
    finally:
        db.close()


def test_product_repository_lists_products_by_name_and_gets_by_id():
    db = build_session()
    try:
        category = Category(name="Emergency", description=None)
        db.add_all(
            [
                Product(
                    name="Exit route sign",
                    description=None,
                    category=category,
                    base_price=Decimal("12.50"),
                ),
                Product(
                    name="Assembly point sign",
                    description="Outdoor assembly point sign",
                    category=category,
                    base_price=Decimal("18.00"),
                    is_active=False,
                ),
            ]
        )
        db.commit()

        repository = ProductRepository(db)

        products = repository.get_products()
        missing_product = repository.get_product_by_id(999)

        assert [product.name for product in products] == [
            "Assembly point sign",
            "Exit route sign",
        ]
        assert products[0].description == "Outdoor assembly point sign"
        assert products[0].base_price == Decimal("18.00")
        assert products[0].is_active is False
        assert repository.get_product_by_id(products[1].id).name == "Exit route sign"
        assert missing_product is None
    finally:
        db.close()


def test_product_repository_lists_active_products_by_name():
    db = build_session()
    try:
        category = Category(name="Emergency", description=None)
        db.add_all(
            [
                Product(
                    name="Exit route sign",
                    description=None,
                    category=category,
                    base_price=Decimal("12.50"),
                ),
                Product(
                    name="Assembly point sign",
                    description="Outdoor assembly point sign",
                    category=category,
                    base_price=Decimal("18.00"),
                    is_active=False,
                ),
            ]
        )
        db.commit()

        repository = ProductRepository(db)

        products = repository.get_active_products()

        assert [product.name for product in products] == ["Exit route sign"]
    finally:
        db.close()


def test_product_repository_pages_active_products_by_category_with_stable_order():
    db = build_session()
    try:
        warning = Category(name="Warning", description=None)
        emergency = Category(name="Emergency", description=None)
        db.add_all(
            [
                Product(
                    name="Alpha sign",
                    description=None,
                    category=warning,
                    base_price=Decimal("10.00"),
                ),
                Product(
                    name="Alpha sign",
                    description=None,
                    category=warning,
                    base_price=Decimal("11.00"),
                ),
                Product(
                    name="Beta sign",
                    description=None,
                    category=warning,
                    base_price=Decimal("12.00"),
                    is_active=False,
                ),
                Product(
                    name="Gamma sign",
                    description=None,
                    category=emergency,
                    base_price=Decimal("13.00"),
                ),
            ]
        )
        db.commit()

        repository = ProductRepository(db)

        first_page = repository.get_active_products_page(
            category_id=warning.id,
            offset=0,
            limit=1,
        )
        second_page = repository.get_active_products_page(
            category_id=warning.id,
            offset=1,
            limit=1,
        )

        assert [product.id for product in first_page] == [1]
        assert [product.id for product in second_page] == [2]
        assert repository.count_active_products(category_id=warning.id) == 2
    finally:
        db.close()


def test_product_repository_gets_active_product_by_id():
    db = build_session()
    try:
        category = Category(name="Emergency", description=None)
        db.add_all(
            [
                Product(
                    name="Exit route sign",
                    description=None,
                    category=category,
                    base_price=Decimal("12.50"),
                ),
                Product(
                    name="Retired sign",
                    description=None,
                    category=category,
                    base_price=Decimal("10.00"),
                    is_active=False,
                ),
            ]
        )
        db.commit()

        repository = ProductRepository(db)

        active_product = repository.get_active_product_by_id(1)
        inactive_product = repository.get_active_product_by_id(2)
        missing_product = repository.get_active_product_by_id(999)

        assert active_product is not None
        assert active_product.name == "Exit route sign"
        assert inactive_product is None
        assert missing_product is None
    finally:
        db.close()


def test_product_service_lists_products_from_repository():
    class FakeProductRepository:
        def get_active_products(self):
            return [
                Product(
                    id=1,
                    name="Exit route sign",
                    description=None,
                    category_id=1,
                    base_price=Decimal("12.50"),
                    is_active=True,
                    created_at=datetime(2026, 4, 26, tzinfo=UTC),
                    updated_at=datetime(2026, 4, 26, tzinfo=UTC),
                )
            ]

        def get_products(self):
            return []

        def get_product_by_id(self, product_id):
            return None

        def get_active_product_by_id(self, product_id):
            return None

    service = ProductService(FakeProductRepository())

    products = service.list_products()

    assert len(products) == 1
    assert products[0].name == "Exit route sign"


def test_product_service_gets_product_from_repository():
    expected_product = Product(
        id=1,
        name="Exit route sign",
        description=None,
        category_id=1,
        base_price=Decimal("12.50"),
        is_active=True,
        created_at=datetime(2026, 4, 26, tzinfo=UTC),
        updated_at=datetime(2026, 4, 26, tzinfo=UTC),
    )

    class FakeProductRepository:
        def get_products(self):
            return []

        def get_product_by_id(self, product_id):
            return None

        def get_active_product_by_id(self, product_id):
            assert product_id == 1
            return expected_product

    service = ProductService(FakeProductRepository())

    product = service.get_product(1)

    assert product == expected_product


def test_list_products_endpoint_returns_active_catalog_products():
    db = build_session()
    category = Category(name="Warning", description="Warning signs")
    db.add_all(
        [
            Product(
                name="Electrical hazard sign",
                description="Warning sign for electrical risk.",
                category=category,
                base_price=Decimal("20.00"),
            ),
            Product(
                name="Retired warning sign",
                description="No longer sold.",
                category=category,
                base_price=Decimal("15.00"),
                is_active=False,
            ),
        ]
    )
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_provider_adapter():
        return LocalMockProviderAdapter(
            {
                (CatalogItemType.PRODUCT, 1): LocalProviderFixture(
                    availability_state=AvailabilityState.AVAILABLE,
                    provider_cost=Decimal("12.50"),
                    supports_requested_configuration=True,
                )
            }
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = override_provider_adapter

    try:

        async def get_products():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get("/api/v1/catalog/products")

        response = asyncio.run(get_products())

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "id": 1,
                    "name": "Electrical hazard sign",
                    "description": "Warning sign for electrical risk.",
                    "category_id": 1,
                    "base_price": "20.00",
                    "availability_state": "available",
                    "direct_checkout_eligible": True,
                    "eligibility_reason": None,
                    "production_lead_time_days": 5,
                    "dispatch_lead_time_days": 1,
                }
            ],
            "meta": {
                "page": 1,
                "page_size": 20,
                "total_items": 1,
                "total_pages": 1,
            },
        }
        assert "is_active" not in response.json()["data"][0]
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_products_endpoint_returns_default_paginated_catalog_products():
    db = build_session()
    try:
        category = seed_category(db)
        for number in range(1, 22):
            seed_product(db, category, name=f"Product {number:02d}")
        configure_product_endpoint_test(db)

        response = asyncio.run(request_product_list())

        assert response.status_code == 200
        payload = response.json()
        assert [product["name"] for product in payload["data"]] == [
            f"Product {number:02d}" for number in range(1, 21)
        ]
        assert payload["meta"] == {
            "page": 1,
            "page_size": 20,
            "total_items": 21,
            "total_pages": 2,
        }
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_products_endpoint_applies_valid_page_and_page_size_slice():
    db = build_session()
    try:
        category = seed_category(db)
        for name in ["Alpha sign", "Alpha sign", "Beta sign", "Delta sign"]:
            seed_product(db, category, name=name)
        configure_product_endpoint_test(db)

        response = asyncio.run(request_product_list({"page": 2, "page_size": 2}))

        assert response.status_code == 200
        payload = response.json()
        assert [product["id"] for product in payload["data"]] == [3, 4]
        assert [product["name"] for product in payload["data"]] == [
            "Beta sign",
            "Delta sign",
        ]
        assert payload["meta"] == {
            "page": 2,
            "page_size": 2,
            "total_items": 4,
            "total_pages": 2,
        }
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_products_endpoint_filters_by_category_id():
    db = build_session()
    try:
        warning = seed_category(db, "Warning")
        emergency = seed_category(db, "Emergency")
        seed_product(db, warning, name="Warning sign")
        seed_product(db, emergency, name="Emergency sign")
        configure_product_endpoint_test(db)

        response = asyncio.run(request_product_list({"category_id": emergency.id}))

        assert response.status_code == 200
        payload = response.json()
        assert [product["name"] for product in payload["data"]] == ["Emergency sign"]
        assert payload["data"][0]["category_id"] == emergency.id
        assert payload["meta"] == {
            "page": 1,
            "page_size": 20,
            "total_items": 1,
            "total_pages": 1,
        }
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_products_endpoint_returns_empty_page_for_category_without_visible_products():
    db = build_session()
    try:
        category = seed_category(db)
        seed_product(db, category, name="Retired sign", is_active=False)
        configure_product_endpoint_test(db)

        response = asyncio.run(request_product_list({"category_id": category.id}))

        assert response.status_code == 200
        assert response.json() == {
            "data": [],
            "meta": {
                "page": 1,
                "page_size": 20,
                "total_items": 0,
                "total_pages": 0,
            },
        }
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "params",
    [
        {"category_id": 0},
        {"category_id": -1},
        {"page": 0},
        {"page": -1},
        {"page_size": 0},
        {"page_size": -1},
        {"page_size": 51},
    ],
)
def test_list_products_endpoint_rejects_invalid_filter_and_pagination_values(params):
    db = build_session()
    try:
        configure_product_endpoint_test(db)

        response = asyncio.run(request_product_list(params))

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_products_endpoint_rejects_unknown_query_parameters():
    db = build_session()
    try:
        configure_product_endpoint_test(db)

        response = asyncio.run(
            request_product_list({"availability_state": "available"})
        )

        assert response.status_code == 422
        assert response.json()["detail"] == {
            "code": "unsupported_query_parameter",
            "message": "Unsupported query parameter.",
            "unsupported_parameters": ["availability_state"],
        }
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_products_endpoint_excludes_inactive_products_with_and_without_category_filter():
    db = build_session()
    try:
        category = seed_category(db)
        seed_product(db, category, name="Active sign")
        seed_product(db, category, name="Retired sign", is_active=False)
        configure_product_endpoint_test(db)

        unfiltered_response = asyncio.run(request_product_list())
        filtered_response = asyncio.run(
            request_product_list({"category_id": category.id})
        )

        assert unfiltered_response.status_code == 200
        assert filtered_response.status_code == 200
        assert [product["name"] for product in unfiltered_response.json()["data"]] == [
            "Active sign"
        ]
        assert [product["name"] for product in filtered_response.json()["data"]] == [
            "Active sign"
        ]
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_products_endpoint_is_documented_in_openapi():
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
    operation = schema["paths"]["/api/v1/catalog/products"]["get"]
    assert operation["summary"] == "List catalog products"
    assert {parameter["name"] for parameter in operation["parameters"]} == {
        "category_id",
        "page",
        "page_size",
    }
    assert "200" in operation["responses"]
    assert "422" in operation["responses"]


def test_get_product_endpoint_returns_active_catalog_product():
    db = build_session()
    category = Category(name="Warning", description="Warning signs")
    db.add(
        Product(
            name="Electrical hazard sign",
            description="Warning sign for electrical risk.",
            category=category,
            base_price=Decimal("20.00"),
        )
    )
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_provider_adapter():
        return LocalMockProviderAdapter(
            {
                (CatalogItemType.PRODUCT, 1): LocalProviderFixture(
                    availability_state=AvailabilityState.AVAILABLE,
                    provider_cost=Decimal("12.50"),
                    supports_requested_configuration=True,
                )
            }
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = override_provider_adapter

    try:

        async def get_product():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get("/api/v1/catalog/products/1")

        response = asyncio.run(get_product())

        assert response.status_code == 200
        assert response.json() == {
            "id": 1,
            "name": "Electrical hazard sign",
            "description": "Warning sign for electrical risk.",
            "category_id": 1,
            "base_price": "20.00",
            "availability_state": "available",
            "direct_checkout_eligible": True,
            "eligibility_reason": None,
            "production_lead_time_days": 5,
            "dispatch_lead_time_days": 1,
        }
        assert "is_active" not in response.json()
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_product_endpoint_marks_missing_adapter_fixture_not_purchasable():
    db = build_session()
    category = Category(name="Warning", description="Warning signs")
    db.add(
        Product(
            name="Electrical hazard sign",
            description="Warning sign for electrical risk.",
            category=category,
            base_price=Decimal("20.00"),
        )
    )
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:

        async def get_product():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get("/api/v1/catalog/products/1")

        response = asyncio.run(get_product())

        assert response.status_code == 200
        payload = response.json()
        assert payload["availability_state"] == "unsupported"
        assert payload["direct_checkout_eligible"] is False
        assert payload["eligibility_reason"] == "missing_local_provider_fixture"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_product_endpoint_marks_unavailable_product_not_purchasable():
    db = build_session()
    category = Category(name="Warning", description="Warning signs")
    db.add(
        Product(
            name="Electrical hazard sign",
            description="Warning sign for electrical risk.",
            category=category,
            base_price=Decimal("20.00"),
        )
    )
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_provider_adapter():
        return LocalMockProviderAdapter(
            {
                (CatalogItemType.PRODUCT, 1): LocalProviderFixture(
                    availability_state=AvailabilityState.TEMPORARILY_UNAVAILABLE,
                    provider_cost=Decimal("12.50"),
                    supports_requested_configuration=True,
                    reason_code="temporarily_unavailable",
                )
            }
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = override_provider_adapter

    try:

        async def get_product():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get("/api/v1/catalog/products/1")

        response = asyncio.run(get_product())

        assert response.status_code == 200
        payload = response.json()
        assert payload["availability_state"] == "temporarily_unavailable"
        assert payload["direct_checkout_eligible"] is False
        assert payload["eligibility_reason"] == "temporarily_unavailable"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_product_endpoint_marks_manual_quote_product_not_purchasable():
    db = build_session()
    category = Category(name="Custom", description="Custom signs")
    db.add(
        Product(
            name="Custom oversized sign",
            description="Requires manual confirmation.",
            category=category,
            base_price=Decimal("99.00"),
        )
    )
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_provider_adapter():
        return LocalMockProviderAdapter(
            {
                (CatalogItemType.PRODUCT, 1): LocalProviderFixture(
                    availability_state=AvailabilityState.MANUAL_QUOTE_REQUIRED,
                    provider_cost=None,
                    supports_requested_configuration=False,
                    reason_code="manual_quote_required",
                )
            }
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = override_provider_adapter

    try:

        async def get_product():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get("/api/v1/catalog/products/1")

        response = asyncio.run(get_product())

        assert response.status_code == 200
        payload = response.json()
        assert payload["availability_state"] == "manual_quote_required"
        assert payload["direct_checkout_eligible"] is False
        assert payload["eligibility_reason"] == "manual_quote_required"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_products_endpoint_marks_outsourced_product_not_purchasable():
    db = build_session()
    category = Category(name="Outsourced", description="Outsourced signs")
    db.add(
        Product(
            name="Special outsourced sign",
            description="Not safe for MVP direct checkout.",
            category=category,
            base_price=Decimal("40.00"),
        )
    )
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_provider_adapter():
        return LocalMockProviderAdapter(
            {
                (CatalogItemType.PRODUCT, 1): LocalProviderFixture(
                    availability_state=AvailabilityState.OUTSOURCED_NOT_MVP_DIRECT,
                    provider_cost=Decimal("25.00"),
                    supports_requested_configuration=True,
                    reason_code="outsourced_not_mvp_direct",
                )
            }
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = override_provider_adapter

    try:

        async def get_products():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get("/api/v1/catalog/products")

        response = asyncio.run(get_products())

        assert response.status_code == 200
        payload = response.json()["data"][0]
        assert payload["availability_state"] == "outsourced_not_mvp_direct"
        assert payload["direct_checkout_eligible"] is False
        assert payload["eligibility_reason"] == "outsourced_not_mvp_direct"
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("fixture", "expected_state", "expected_reason"),
    [
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.TEMPORARILY_UNAVAILABLE,
                provider_cost=Decimal("12.50"),
                supports_requested_configuration=True,
                reason_code="temporarily_unavailable",
            ),
            "temporarily_unavailable",
            "temporarily_unavailable",
        ),
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.MANUAL_QUOTE_REQUIRED,
                provider_cost=None,
                supports_requested_configuration=False,
                reason_code="manual_quote_required",
            ),
            "manual_quote_required",
            "manual_quote_required",
        ),
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.OUTSOURCED_NOT_MVP_DIRECT,
                provider_cost=Decimal("25.00"),
                supports_requested_configuration=True,
                reason_code="outsourced_not_mvp_direct",
            ),
            "outsourced_not_mvp_direct",
            "outsourced_not_mvp_direct",
        ),
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.AVAILABLE,
                provider_cost=None,
                supports_requested_configuration=True,
                reason_code="provider_cost_missing",
            ),
            "available",
            "provider_cost_missing",
        ),
    ],
)
def test_list_products_endpoint_preserves_backend_eligibility_when_filtered_and_paginated(
    fixture,
    expected_state,
    expected_reason,
):
    db = build_session()
    try:
        category = seed_category(db)
        product = seed_product(db, category, name="Eligibility checked sign")
        configure_product_endpoint_test(
            db,
            {
                (CatalogItemType.PRODUCT, product.id): fixture,
            },
        )

        response = asyncio.run(
            request_product_list(
                {
                    "category_id": category.id,
                    "page": 1,
                    "page_size": 1,
                }
            )
        )

        assert response.status_code == 200
        payload = response.json()["data"][0]
        assert payload["availability_state"] == expected_state
        assert payload["direct_checkout_eligible"] is False
        assert payload["eligibility_reason"] == expected_reason
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_products_endpoint_does_not_expose_internal_provider_fields():
    db = build_session()
    try:
        category = seed_category(db)
        product = seed_product(db, category, name="Customer safe sign")
        configure_product_endpoint_test(
            db,
            {
                (CatalogItemType.PRODUCT, product.id): LocalProviderFixture(
                    availability_state=AvailabilityState.AVAILABLE,
                    provider_cost=Decimal("0.01"),
                    supports_requested_configuration=True,
                )
            },
        )

        response = asyncio.run(request_product_list())

        assert response.status_code == 200
        payload = response.json()["data"][0]
        assert "provider_cost" not in payload
        assert "assigned_provider_id" not in payload
        assert "provider_pricing_reference" not in payload
        assert "is_active" not in payload
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_product_endpoint_ignores_frontend_eligibility_claims():
    db = build_session()
    category = Category(name="Custom", description="Custom signs")
    db.add(
        Product(
            name="Custom oversized sign",
            description="Requires manual confirmation.",
            category=category,
            base_price=Decimal("99.00"),
        )
    )
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_provider_adapter():
        return LocalMockProviderAdapter(
            {
                (CatalogItemType.PRODUCT, 1): LocalProviderFixture(
                    availability_state=AvailabilityState.MANUAL_QUOTE_REQUIRED,
                    provider_cost=None,
                    supports_requested_configuration=False,
                    production_days=12,
                    dispatch_days=3,
                    reason_code="manual_quote_required",
                )
            }
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = override_provider_adapter

    try:

        async def get_product():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get(
                    "/api/v1/catalog/products/1",
                    params={
                        "availability_state": "available",
                        "direct_checkout_eligible": "true",
                        "provider_cost": "0.01",
                        "production_lead_time_days": "1",
                        "dispatch_lead_time_days": "0",
                        "base_price": "0.01",
                    },
                )

        response = asyncio.run(get_product())

        assert response.status_code == 200
        payload = response.json()
        assert payload["availability_state"] == "manual_quote_required"
        assert payload["direct_checkout_eligible"] is False
        assert payload["eligibility_reason"] == "manual_quote_required"
        assert payload["production_lead_time_days"] == 12
        assert payload["dispatch_lead_time_days"] == 3
        assert payload["base_price"] == "99.00"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_product_endpoint_returns_404_for_missing_product():
    db = build_session()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:

        async def get_product():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get("/api/v1/catalog/products/999")

        response = asyncio.run(get_product())

        assert response.status_code == 404
        assert response.json() == {"detail": "Product not found"}
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_product_endpoint_returns_404_for_inactive_product():
    db = build_session()
    category = Category(name="Warning", description="Warning signs")
    db.add(
        Product(
            name="Retired warning sign",
            description="No longer sold.",
            category=category,
            base_price=Decimal("15.00"),
            is_active=False,
        )
    )
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:

        async def get_product():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get("/api/v1/catalog/products/1")

        response = asyncio.run(get_product())

        assert response.status_code == 404
        assert response.json() == {"detail": "Product not found"}
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_product_endpoint_is_documented_in_openapi():
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
    operation = schema["paths"]["/api/v1/catalog/products/{product_id}"]["get"]
    assert operation["summary"] == "Get catalog product"
    assert "200" in operation["responses"]
    assert "404" in operation["responses"]
