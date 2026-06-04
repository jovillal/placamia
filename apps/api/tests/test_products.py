import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import httpx
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
            ]
        }
        assert "is_active" not in response.json()["data"][0]
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
    assert "200" in operation["responses"]


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
