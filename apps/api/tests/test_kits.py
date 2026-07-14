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
from app.models.kit import Kit
from app.models.kit_item import KitItem
from app.models.product import Product
from app.repositories.kit_repository import KitRepository
from app.services.kit_eligibility_service import (
    KIT_CONTENTS_UNAVAILABLE_REASON,
    KitEligibilityService,
)
from app.services.kit_service import KitService
from sqlalchemy import create_engine, inspect, select
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


async def request_kits(params: dict[str, str] | None = None):
    """Call the public kit list endpoint through the ASGI test transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get("/api/v1/catalog/kits", params=params)


def build_provider_adapter_override(fixtures):
    """Build a FastAPI dependency override for deterministic adapter fixtures."""

    async def override_provider_adapter():
        return LocalMockProviderAdapter(fixtures)

    return override_provider_adapter


def available_fixture(cost: str = "12.50") -> LocalProviderFixture:
    """Return a direct-checkout eligible local provider fixture."""
    return LocalProviderFixture(
        availability_state=AvailabilityState.AVAILABLE,
        provider_cost=Decimal(cost),
        supports_requested_configuration=True,
    )


def catalog_persistence_snapshot(db):
    """Return stored catalog rows for read-only endpoint assertions."""
    return {
        table.name: db.execute(select(table).order_by(table.c.id)).all()
        for table in (
            Category.__table__,
            Product.__table__,
            Kit.__table__,
            KitItem.__table__,
        )
    }


def test_kit_model_persists_catalog_bundle():
    db = build_session()
    try:
        kit = Kit(
            name="Emergency evacuation kit",
            description="Common signage for evacuation routes.",
        )
        db.add(kit)
        db.commit()
        db.refresh(kit)

        assert kit.id == 1
        assert kit.name == "Emergency evacuation kit"
        assert kit.description == "Common signage for evacuation routes."
        assert kit.is_active is True
        assert kit.created_at is not None
        assert kit.updated_at is not None
    finally:
        db.close()


def test_kit_item_model_links_kit_to_product_with_quantity():
    db = build_session()
    try:
        category = Category(name="Emergency", description=None)
        product = Product(
            name="Exit route sign",
            description=None,
            category=category,
            base_price=Decimal("12.50"),
        )
        kit = Kit(
            name="Emergency evacuation kit",
            description=None,
        )
        kit_item = KitItem(
            kit=kit,
            product=product,
            quantity=4,
        )
        db.add(kit_item)
        db.commit()
        db.refresh(kit)
        db.refresh(product)
        db.refresh(kit_item)

        assert kit_item.id == 1
        assert kit_item.kit_id == kit.id
        assert kit_item.product_id == product.id
        assert kit_item.quantity == 4
        assert kit_item.kit == kit
        assert kit_item.product == product
        assert kit.kit_items == [kit_item]
        assert product.kit_items == [kit_item]
        assert kit_item.created_at is not None
        assert kit_item.updated_at is not None
    finally:
        db.close()


def test_kit_and_kit_item_tables_match_mvp_fields():
    db = build_session()
    try:
        kit_columns = {
            column["name"] for column in inspect(db.bind).get_columns("kits")
        }
        kit_item_columns = {
            column["name"] for column in inspect(db.bind).get_columns("kit_items")
        }

        assert kit_columns == {
            "id",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        }
        assert kit_item_columns == {
            "id",
            "kit_id",
            "product_id",
            "quantity",
            "created_at",
            "updated_at",
        }
    finally:
        db.close()


def test_kit_repository_lists_active_kits_by_name():
    db = build_session()
    try:
        db.add_all(
            [
                Kit(
                    name="Warehouse safety kit",
                    description="Common warehouse safety signage.",
                ),
                Kit(
                    name="Emergency evacuation kit",
                    description=None,
                ),
            ]
        )
        db.commit()

        repository = KitRepository(db)

        kits = repository.get_active_kits()

        assert [kit.name for kit in kits] == [
            "Emergency evacuation kit",
            "Warehouse safety kit",
        ]
        assert all(kit.is_active for kit in kits)
    finally:
        db.close()


def test_kit_repository_excludes_inactive_kits():
    db = build_session()
    try:
        db.add_all(
            [
                Kit(
                    name="Active kit",
                    description=None,
                ),
                Kit(
                    name="Retired kit",
                    description="No longer shown to customers.",
                    is_active=False,
                ),
            ]
        )
        db.commit()

        repository = KitRepository(db)

        kits = repository.get_active_kits()

        assert [kit.name for kit in kits] == ["Active kit"]
    finally:
        db.close()


def test_kit_service_lists_public_items_for_active_products_only():
    active_item = KitItem(
        product=Product(
            id=1,
            name="Exit route sign",
            description=None,
            category_id=1,
            base_price=Decimal("12.50"),
            is_active=True,
            created_at=datetime(2026, 5, 6, tzinfo=UTC),
            updated_at=datetime(2026, 5, 6, tzinfo=UTC),
        ),
        product_id=1,
        quantity=2,
    )
    inactive_item = KitItem(
        product=Product(
            id=2,
            name="Retired sign",
            description=None,
            category_id=1,
            base_price=Decimal("9.00"),
            is_active=False,
            created_at=datetime(2026, 5, 6, tzinfo=UTC),
            updated_at=datetime(2026, 5, 6, tzinfo=UTC),
        ),
        product_id=2,
        quantity=1,
    )
    kit = Kit(
        id=1,
        name="Emergency evacuation kit",
        description=None,
        is_active=True,
        created_at=datetime(2026, 5, 6, tzinfo=UTC),
        updated_at=datetime(2026, 5, 6, tzinfo=UTC),
    )
    kit.kit_items = [inactive_item, active_item]

    class FakeKitRepository:
        def get_active_kits(self):
            return [kit]

    service = KitService(FakeKitRepository())

    items = service.list_public_kit_items(kit)

    assert items == [active_item]


def test_kit_eligibility_uses_customer_safe_reason_for_omitted_inactive_content():
    active_product = Product(
        id=1,
        name="Exit route sign",
        description=None,
        category_id=1,
        base_price=Decimal("12.50"),
        is_active=True,
    )
    inactive_product = Product(
        id=2,
        name="Retired sign",
        description=None,
        category_id=1,
        base_price=Decimal("9.00"),
        is_active=False,
    )
    kit = Kit(id=1, name="Mixed content kit", description=None, is_active=True)
    kit.kit_items = [
        KitItem(product=active_product, product_id=1, quantity=2),
        KitItem(product=inactive_product, product_id=2, quantity=1),
    ]
    provider_adapter = LocalMockProviderAdapter(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("20.00"),
            (CatalogItemType.PRODUCT, active_product.id): available_fixture(),
        }
    )

    eligibility = KitEligibilityService(provider_adapter).evaluate_kit(kit)

    assert eligibility.direct_checkout_eligible is False
    assert eligibility.eligibility_reason == KIT_CONTENTS_UNAVAILABLE_REASON


def test_kit_eligibility_retains_internal_reason_for_all_inactive_contents():
    inactive_product = Product(
        id=1,
        name="Retired sign",
        description=None,
        category_id=1,
        base_price=Decimal("9.00"),
        is_active=False,
    )
    kit = Kit(id=1, name="Retired contents kit", description=None, is_active=True)
    kit.kit_items = [
        KitItem(product=inactive_product, product_id=1, quantity=1),
    ]
    provider_adapter = LocalMockProviderAdapter(
        {(CatalogItemType.KIT, kit.id): available_fixture("20.00")}
    )

    eligibility = KitEligibilityService(provider_adapter).evaluate_kit(kit)

    assert eligibility.direct_checkout_eligible is False
    assert eligibility.eligibility_reason == "inactive_kit_item"


def test_kit_service_lists_kits_from_repository():
    expected_kit = Kit(
        id=1,
        name="Emergency evacuation kit",
        description=None,
        is_active=True,
        created_at=datetime(2026, 5, 6, tzinfo=UTC),
        updated_at=datetime(2026, 5, 6, tzinfo=UTC),
    )

    class FakeKitRepository:
        def get_active_kits(self):
            return [expected_kit]

    service = KitService(FakeKitRepository())

    kits = service.list_kits()

    assert kits == [expected_kit]


def test_kit_service_lists_public_kits_with_active_required_contents_only():
    active_product = Product(
        id=1,
        name="Exit route sign",
        description=None,
        category_id=1,
        base_price=Decimal("12.50"),
        is_active=True,
        created_at=datetime(2026, 5, 6, tzinfo=UTC),
        updated_at=datetime(2026, 5, 6, tzinfo=UTC),
    )
    inactive_product = Product(
        id=2,
        name="Retired sign",
        description=None,
        category_id=1,
        base_price=Decimal("9.00"),
        is_active=False,
        created_at=datetime(2026, 5, 6, tzinfo=UTC),
        updated_at=datetime(2026, 5, 6, tzinfo=UTC),
    )
    visible_kit = Kit(
        id=1,
        name="Visible kit",
        description=None,
        is_active=True,
        created_at=datetime(2026, 5, 6, tzinfo=UTC),
        updated_at=datetime(2026, 5, 6, tzinfo=UTC),
    )
    visible_kit.kit_items = [
        KitItem(product=inactive_product, product_id=2, quantity=1),
        KitItem(product=active_product, product_id=1, quantity=2),
    ]
    hidden_kit = Kit(
        id=2,
        name="Hidden kit",
        description=None,
        is_active=True,
        created_at=datetime(2026, 5, 6, tzinfo=UTC),
        updated_at=datetime(2026, 5, 6, tzinfo=UTC),
    )
    hidden_kit.kit_items = [KitItem(product=inactive_product, product_id=2, quantity=1)]

    class FakeKitRepository:
        def get_active_kits(self):
            return [hidden_kit, visible_kit]

    service = KitService(FakeKitRepository())

    kits = service.list_public_kits()

    assert kits == [visible_kit]


def test_list_kits_endpoint_omits_inactive_content_with_customer_safe_reason():
    db = build_session()
    category = Category(name="Emergency", description=None)
    active_product = Product(
        name="Exit route sign",
        description=None,
        category=category,
        base_price=Decimal("12.50"),
    )
    inactive_product = Product(
        name="Retired exit sign",
        description=None,
        category=category,
        base_price=Decimal("9.00"),
        is_active=False,
    )
    active_kit = Kit(
        name="Emergency evacuation kit",
        description="Common signage for evacuation routes.",
    )
    inactive_kit = Kit(
        name="Retired kit",
        description=None,
        is_active=False,
    )
    db.add_all(
        [
            KitItem(
                kit=active_kit,
                product=active_product,
                quantity=4,
            ),
            KitItem(
                kit=active_kit,
                product=inactive_product,
                quantity=1,
            ),
            KitItem(
                kit=inactive_kit,
                product=active_product,
                quantity=2,
            ),
        ]
    )
    db.commit()
    persistence_before = catalog_persistence_snapshot(db)

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = build_provider_adapter_override(
        {
            (CatalogItemType.KIT, 1): available_fixture("20.00"),
            (CatalogItemType.PRODUCT, active_product.id): available_fixture(),
        }
    )

    try:
        response = asyncio.run(request_kits())

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "id": 1,
                    "name": "Emergency evacuation kit",
                    "description": "Common signage for evacuation routes.",
                    "items": [
                        {
                            "product_id": active_product.id,
                            "name": "Exit route sign",
                            "description": None,
                            "category_id": category.id,
                            "quantity": 4,
                        }
                    ],
                    "availability_state": "available",
                    "direct_checkout_eligible": False,
                    "eligibility_reason": "kit_contents_unavailable",
                    "production_lead_time_days": 5,
                    "dispatch_lead_time_days": 1,
                }
            ]
        }
        assert catalog_persistence_snapshot(db) == persistence_before
        assert not db.new
        assert not db.dirty
        assert not db.deleted
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_kits_endpoint_marks_eligible_kit_purchasable():
    db = build_session()
    category = Category(name="Emergency", description=None)
    product = Product(
        name="Exit route sign",
        description=None,
        category=category,
        base_price=Decimal("12.50"),
    )
    kit = Kit(
        name="Emergency evacuation kit",
        description="Common signage for evacuation routes.",
    )
    db.add(KitItem(kit=kit, product=product, quantity=4))
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = build_provider_adapter_override(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("20.00"),
            (CatalogItemType.PRODUCT, product.id): available_fixture(),
        }
    )

    try:
        response = asyncio.run(request_kits())

        assert response.status_code == 200
        payload = response.json()["data"][0]
        assert payload["direct_checkout_eligible"] is True
        assert payload["eligibility_reason"] is None
        assert payload["availability_state"] == "available"
        assert payload["production_lead_time_days"] == 5
        assert payload["dispatch_lead_time_days"] == 1
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_kits_endpoint_hides_kit_with_zero_active_required_contents():
    db = build_session()
    category = Category(name="Retired", description=None)
    inactive_product = Product(
        name="Retired sign",
        description=None,
        category=category,
        base_price=Decimal("9.00"),
        is_active=False,
    )
    empty_kit = Kit(
        name="Empty kit",
        description="Still visible under current public behavior.",
    )
    inactive_contents_kit = Kit(
        name="Retired contents kit",
        description=None,
    )
    db.add_all(
        [
            empty_kit,
            KitItem(kit=inactive_contents_kit, product=inactive_product, quantity=1),
        ]
    )
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = build_provider_adapter_override(
        {
            (CatalogItemType.KIT, empty_kit.id): available_fixture("20.00"),
            (CatalogItemType.KIT, inactive_contents_kit.id): available_fixture("20.00"),
        }
    )

    try:
        response = asyncio.run(request_kits())

        assert response.status_code == 200
        assert response.json() == {"data": []}
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_kits_endpoint_marks_unavailable_content_not_purchasable():
    db = build_session()
    category = Category(name="Emergency", description=None)
    product = Product(
        name="Exit route sign",
        description=None,
        category=category,
        base_price=Decimal("12.50"),
    )
    kit = Kit(name="Emergency evacuation kit", description=None)
    db.add(KitItem(kit=kit, product=product, quantity=4))
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = build_provider_adapter_override(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("20.00"),
            (CatalogItemType.PRODUCT, product.id): LocalProviderFixture(
                availability_state=AvailabilityState.TEMPORARILY_UNAVAILABLE,
                provider_cost=Decimal("12.50"),
                supports_requested_configuration=True,
                reason_code="temporarily_unavailable",
            ),
        }
    )

    try:
        response = asyncio.run(request_kits())

        assert response.status_code == 200
        payload = response.json()["data"][0]
        assert payload["items"] == [
            {
                "product_id": product.id,
                "name": "Exit route sign",
                "description": None,
                "category_id": category.id,
                "quantity": 4,
            }
        ]
        assert payload["direct_checkout_eligible"] is False
        assert payload["eligibility_reason"] == "temporarily_unavailable"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_kits_endpoint_omits_inactive_content_but_retains_unavailable_active_content():
    db = build_session()
    category = Category(name="Emergency", description=None)
    unavailable_product = Product(
        name="Temporarily unavailable sign",
        description=None,
        category=category,
        base_price=Decimal("12.50"),
    )
    inactive_product = Product(
        name="Retired sign",
        description=None,
        category=category,
        base_price=Decimal("9.00"),
        is_active=False,
    )
    kit = Kit(name="Mixed availability kit", description=None)
    db.add_all(
        [
            KitItem(kit=kit, product=inactive_product, quantity=1),
            KitItem(kit=kit, product=unavailable_product, quantity=2),
        ]
    )
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = build_provider_adapter_override(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("20.00"),
            (CatalogItemType.PRODUCT, unavailable_product.id): LocalProviderFixture(
                availability_state=AvailabilityState.TEMPORARILY_UNAVAILABLE,
                provider_cost=Decimal("12.50"),
                supports_requested_configuration=True,
                reason_code="temporarily_unavailable",
            ),
        }
    )

    try:
        response = asyncio.run(request_kits())

        assert response.status_code == 200
        payload = response.json()["data"][0]
        assert payload["items"] == [
            {
                "product_id": unavailable_product.id,
                "name": "Temporarily unavailable sign",
                "description": None,
                "category_id": category.id,
                "quantity": 2,
            }
        ]
        assert payload["direct_checkout_eligible"] is False
        assert payload["eligibility_reason"] == "temporarily_unavailable"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_kits_endpoint_marks_manual_quote_content_not_purchasable():
    db = build_session()
    category = Category(name="Custom", description=None)
    product = Product(
        name="Oversized custom sign",
        description=None,
        category=category,
        base_price=Decimal("99.00"),
    )
    kit = Kit(name="Custom kit", description=None)
    db.add(KitItem(kit=kit, product=product, quantity=1))
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = build_provider_adapter_override(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("20.00"),
            (CatalogItemType.PRODUCT, product.id): LocalProviderFixture(
                availability_state=AvailabilityState.MANUAL_QUOTE_REQUIRED,
                provider_cost=None,
                supports_requested_configuration=False,
                reason_code="manual_quote_required",
            ),
        }
    )

    try:
        response = asyncio.run(request_kits())

        assert response.status_code == 200
        payload = response.json()["data"][0]
        assert payload["items"] == [
            {
                "product_id": product.id,
                "name": "Oversized custom sign",
                "description": None,
                "category_id": category.id,
                "quantity": 1,
            }
        ]
        assert payload["direct_checkout_eligible"] is False
        assert payload["eligibility_reason"] == "manual_quote_required"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_kits_endpoint_marks_non_priceable_content_not_purchasable():
    db = build_session()
    category = Category(name="Emergency", description=None)
    product = Product(
        name="Exit route sign",
        description=None,
        category=category,
        base_price=Decimal("12.50"),
    )
    kit = Kit(name="Emergency evacuation kit", description=None)
    db.add(KitItem(kit=kit, product=product, quantity=4))
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = build_provider_adapter_override(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("20.00"),
            (CatalogItemType.PRODUCT, product.id): LocalProviderFixture(
                availability_state=AvailabilityState.AVAILABLE,
                provider_cost=None,
                supports_requested_configuration=True,
                reason_code="provider_cost_missing",
            ),
        }
    )

    try:
        response = asyncio.run(request_kits())

        assert response.status_code == 200
        payload = response.json()["data"][0]
        assert payload["items"] == [
            {
                "product_id": product.id,
                "name": "Exit route sign",
                "description": None,
                "category_id": category.id,
                "quantity": 4,
            }
        ]
        assert payload["direct_checkout_eligible"] is False
        assert payload["eligibility_reason"] == "provider_cost_missing"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_kits_endpoint_marks_outsourced_content_not_purchasable():
    db = build_session()
    category = Category(name="Outsourced", description=None)
    product = Product(
        name="Special outsourced sign",
        description=None,
        category=category,
        base_price=Decimal("40.00"),
    )
    kit = Kit(name="Outsourced kit", description=None)
    db.add(KitItem(kit=kit, product=product, quantity=1))
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = build_provider_adapter_override(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("20.00"),
            (CatalogItemType.PRODUCT, product.id): LocalProviderFixture(
                availability_state=AvailabilityState.OUTSOURCED_NOT_MVP_DIRECT,
                provider_cost=Decimal("25.00"),
                supports_requested_configuration=True,
                reason_code="outsourced_not_mvp_direct",
            ),
        }
    )

    try:
        response = asyncio.run(request_kits())

        assert response.status_code == 200
        payload = response.json()["data"][0]
        assert payload["items"] == [
            {
                "product_id": product.id,
                "name": "Special outsourced sign",
                "description": None,
                "category_id": category.id,
                "quantity": 1,
            }
        ]
        assert payload["direct_checkout_eligible"] is False
        assert payload["eligibility_reason"] == "outsourced_not_mvp_direct"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_kits_endpoint_ignores_frontend_eligibility_claims():
    db = build_session()
    category = Category(name="Custom", description=None)
    product = Product(
        name="Oversized custom sign",
        description=None,
        category=category,
        base_price=Decimal("99.00"),
    )
    kit = Kit(name="Custom kit", description=None)
    db.add(KitItem(kit=kit, product=product, quantity=1))
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = build_provider_adapter_override(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("20.00"),
            (CatalogItemType.PRODUCT, product.id): LocalProviderFixture(
                availability_state=AvailabilityState.MANUAL_QUOTE_REQUIRED,
                provider_cost=None,
                supports_requested_configuration=False,
                production_days=12,
                dispatch_days=3,
                reason_code="manual_quote_required",
            ),
        }
    )

    try:
        response = asyncio.run(
            request_kits(
                params={
                    "items": "[]",
                    "availability_state": "available",
                    "direct_checkout_eligible": "true",
                    "provider_cost": "0.01",
                    "supports_requested_configuration": "true",
                    "production_lead_time_days": "1",
                    "dispatch_lead_time_days": "0",
                }
            )
        )

        assert response.status_code == 200
        payload = response.json()["data"][0]
        assert payload["items"] == [
            {
                "product_id": product.id,
                "name": "Oversized custom sign",
                "description": None,
                "category_id": category.id,
                "quantity": 1,
            }
        ]
        assert payload["direct_checkout_eligible"] is False
        assert payload["eligibility_reason"] == "manual_quote_required"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_kits_endpoint_does_not_expose_internal_provider_or_product_fields():
    db = build_session()
    category = Category(name="Emergency", description=None)
    product = Product(
        name="Exit route sign",
        description="Customer-safe description",
        category=category,
        base_price=Decimal("12.50"),
    )
    kit = Kit(name="Emergency evacuation kit", description=None)
    db.add(KitItem(kit=kit, product=product, quantity=4))
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = build_provider_adapter_override(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("20.00"),
            (CatalogItemType.PRODUCT, product.id): available_fixture(),
        }
    )

    try:
        response = asyncio.run(request_kits())

        assert response.status_code == 200
        payload = response.json()["data"][0]
        item_payload = payload["items"][0]
        assert "provider_cost" not in payload
        assert "assigned_provider_id" not in payload
        assert "supports_requested_configuration" not in payload
        assert "provider_cost" not in item_payload
        assert "assigned_provider_id" not in item_payload
        assert "supports_requested_configuration" not in item_payload
        assert "base_price" not in item_payload
        assert "is_active" not in item_payload
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_kits_endpoint_is_documented_in_openapi():
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
    operation = schema["paths"]["/api/v1/catalog/kits"]["get"]
    assert operation["summary"] == "List catalog kits"
    assert "200" in operation["responses"]
