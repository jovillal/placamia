import asyncio
from decimal import Decimal

import httpx
import pytest
from app.api.dependencies import get_optional_current_user, get_provider_adapter
from app.core.config import settings
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
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.template import Template
from app.models.template_field import TemplateField
from app.models.user import User
from app.services.auth_service import AuthService
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


async def post_pricing_quote(
    payload: dict[str, object],
    headers: dict[str, str] | None = None,
):
    """Call the pricing quote endpoint through the ASGI test transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post(
            "/api/v1/pricing/quotes",
            json=payload,
            headers=headers,
        )


def available_fixture(cost: str = "12.00") -> LocalProviderFixture:
    """Return a direct-checkout eligible local provider fixture."""
    return LocalProviderFixture(
        availability_state=AvailabilityState.AVAILABLE,
        provider_cost=Decimal(cost),
        supports_requested_configuration=True,
    )


class RecordingProviderAdapter(LocalMockProviderAdapter):
    """Record provider reads made by endpoint pricing orchestration."""

    def __init__(self, fixtures) -> None:
        super().__init__(fixtures)
        self.requests = []

    def check_availability(self, request):
        self.requests.append(("availability", request))
        return super().check_availability(request)

    def quote_pricing(self, request):
        self.requests.append(("pricing", request))
        return super().quote_pricing(request)

    def check_direct_checkout_eligibility(self, request):
        self.requests.append(("eligibility", request))
        return super().check_direct_checkout_eligibility(request)

    def estimate_lead_time(self, request):
        self.requests.append(("lead_time", request))
        return super().estimate_lead_time(request)


def seed_user(db, email: str = "designer@example.com") -> User:
    """Persist one customer for authenticated Design pricing tests."""
    user = User(email=email, full_name="Design Customer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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


def seed_design(db, *, owner: User, product: Product) -> Design:
    """Persist one valid Design with a Product-backed active Template."""
    template = Template(
        product=product,
        name="Emergency exit template",
        description=None,
    )
    template.template_fields = [
        TemplateField(
            field_name="legend",
            field_type="text",
            is_required=True,
            allowed_values=None,
            display_order=1,
        ),
        TemplateField(
            field_name="width_cm",
            field_type="number",
            is_required=True,
            allowed_values=None,
            display_order=2,
        ),
    ]
    design = Design(
        customer=owner,
        template=template,
        customization_values={"legend": "Emergency exit", "width_cm": 30},
    )
    db.add(design)
    db.commit()
    db.refresh(design)
    return design


def persistence_snapshot(db) -> dict[str, list[tuple[object, ...]]]:
    """Return pricing-related persisted state for read-only assertions."""
    return {
        "products": db.execute(select(Product.__table__).order_by(Product.id)).all(),
        "kits": db.execute(select(Kit.__table__).order_by(Kit.id)).all(),
        "kit_items": db.execute(select(KitItem.__table__).order_by(KitItem.id)).all(),
        "templates": db.execute(select(Template.__table__).order_by(Template.id)).all(),
        "template_fields": db.execute(
            select(TemplateField.__table__).order_by(TemplateField.id)
        ).all(),
        "designs": db.execute(select(Design.__table__).order_by(Design.id)).all(),
        "orders": db.execute(select(Order.__table__).order_by(Order.id)).all(),
        "order_items": db.execute(
            select(OrderItem.__table__).order_by(OrderItem.id)
        ).all(),
        "payments": db.execute(select(Payment.__table__).order_by(Payment.id)).all(),
    }


def table_count(db, model) -> int:
    """Return the number of persisted rows for a model."""
    return db.scalar(select(func.count()).select_from(model))


def configure_pricing_endpoint_test(db, fixtures, current_user=None):
    """Install FastAPI dependency overrides for one pricing endpoint test."""
    configure_pricing_endpoint_test_with_adapter(
        db,
        LocalMockProviderAdapter(fixtures),
        current_user,
    )


def configure_pricing_endpoint_test_with_adapter(
    db,
    provider_adapter,
    current_user=None,
):
    """Install FastAPI overrides with a caller-owned provider adapter."""

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    async def override_provider_adapter():
        return provider_adapter

    async def override_optional_current_user():
        return current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_provider_adapter] = override_provider_adapter
    app.dependency_overrides[get_optional_current_user] = override_optional_current_user


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


def test_pricing_quote_endpoint_hides_mixed_inactive_required_kit_content():
    db = build_session()
    active_product = seed_product(db)
    inactive_product = Product(
        name="Inactive internal sign",
        description=None,
        category_id=active_product.category_id,
        base_price=Decimal("999.99"),
        is_active=False,
    )
    db.add(inactive_product)
    db.commit()
    db.refresh(inactive_product)
    kit = seed_kit(db, [(active_product, 1), (inactive_product, 1)])
    configure_pricing_endpoint_test(
        db,
        {
            (CatalogItemType.KIT, kit.id): available_fixture("30.00"),
            (CatalogItemType.PRODUCT, active_product.id): available_fixture("12.00"),
        },
    )
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
        payload = response.json()
        assert payload == {
            "detail": {
                "code": "kit_contents_unavailable",
                "message": "Kit is not eligible for direct checkout pricing.",
            }
        }
        assert set(payload) == {"detail"}
        assert "lines" not in response.text
        assert inactive_product.name not in response.text
        assert "999.99" not in response.text
        assert persistence_snapshot(db) == persistence_before
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_pricing_quote_endpoint_returns_owned_design_preview():
    db = build_session()
    owner = seed_user(db)
    product = seed_product(db, base_price="25.00")
    design = seed_design(db, owner=owner, product=product)
    adapter = RecordingProviderAdapter(
        {(CatalogItemType.DESIGN, design.id): available_fixture("15.00")}
    )
    configure_pricing_endpoint_test_with_adapter(db, adapter, owner)
    persistence_before = persistence_snapshot(db)

    try:
        response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "design",
                    "item_id": design.id,
                    "quantity": 3,
                }
            )
        )

        assert response.status_code == 200
        assert response.json() == {
            "item_type": "design",
            "item_id": design.id,
            "quantity": 3,
            "currency": "COP",
            "customer_unit_price": "25.00",
            "customer_subtotal": "75.00",
            "preview_total": "75.00",
            "pricing_rule": "temporary_design_product_base_price_v1",
            "provider_quote_reference": f"local-quote-design-{design.id}",
        }
        assert all(
            request.item_type is CatalogItemType.DESIGN
            and request.options == design.customization_values
            for _, request in adapter.requests
        )
        assert persistence_snapshot(db) == persistence_before
        assert adapter.handoffs_by_key == {}
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_pricing_quote_endpoint_requires_authentication_for_design_only():
    db = build_session()
    product = seed_product(db)
    kit = seed_kit(db, [(product, 1)])
    configure_pricing_endpoint_test(
        db,
        {
            (CatalogItemType.PRODUCT, product.id): available_fixture("12.00"),
            (CatalogItemType.KIT, kit.id): available_fixture("20.00"),
        },
    )

    try:
        design_response = asyncio.run(
            post_pricing_quote({"item_type": "design", "item_id": 1, "quantity": 1})
        )
        product_response = asyncio.run(
            post_pricing_quote(
                {"item_type": "product", "item_id": product.id, "quantity": 1}
            )
        )
        kit_response = asyncio.run(
            post_pricing_quote({"item_type": "kit", "item_id": kit.id, "quantity": 1})
        )

        assert design_response.status_code == 401
        assert product_response.status_code == 200
        assert kit_response.status_code == 200
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_pricing_quote_endpoint_rejects_invalid_design_bearer_token(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_TOKEN_SECRET", "test-token-secret")
    db = build_session()
    configure_pricing_endpoint_test(db, {})
    del app.dependency_overrides[get_optional_current_user]

    try:
        response = asyncio.run(
            post_pricing_quote(
                {"item_type": "design", "item_id": 1, "quantity": 1},
                headers={"Authorization": "Bearer invalid-token"},
            )
        )

        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid authentication credentials"}
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_pricing_quote_endpoint_accepts_valid_design_bearer_token(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_TOKEN_SECRET", "test-token-secret")
    db = build_session()
    owner = seed_user(db)
    design = seed_design(db, owner=owner, product=seed_product(db))
    adapter = RecordingProviderAdapter(
        {(CatalogItemType.DESIGN, design.id): available_fixture("12.00")}
    )
    configure_pricing_endpoint_test_with_adapter(db, adapter, owner)
    del app.dependency_overrides[get_optional_current_user]
    token = AuthService(settings.AUTH_TOKEN_SECRET).create_access_token(owner.id)
    persistence_before = persistence_snapshot(db)

    try:
        response = asyncio.run(
            post_pricing_quote(
                {"item_type": "design", "item_id": design.id, "quantity": 1},
                headers={"Authorization": f"Bearer {token}"},
            )
        )

        assert response.status_code == 200
        assert response.json()["item_id"] == design.id
        assert persistence_snapshot(db) == persistence_before
        assert adapter.handoffs_by_key == {}
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_pricing_quote_endpoint_hides_cross_user_and_unknown_designs_identically():
    db = build_session()
    owner = seed_user(db, "owner@example.com")
    other_customer = seed_user(db, "other@example.com")
    design = seed_design(db, owner=owner, product=seed_product(db))
    configure_pricing_endpoint_test(db, {}, other_customer)

    try:
        cross_user_response = asyncio.run(
            post_pricing_quote(
                {"item_type": "design", "item_id": design.id, "quantity": 1}
            )
        )
        unknown_response = asyncio.run(
            post_pricing_quote({"item_type": "design", "item_id": 999, "quantity": 1})
        )

        assert cross_user_response.status_code == 404
        assert unknown_response.status_code == 404
        assert cross_user_response.json() == {
            "detail": {
                "code": "design_not_found",
                "message": "Design not found.",
            }
        }
        assert unknown_response.json() == cross_user_response.json()
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "extra_claim",
    [
        {"customization_values": {"legend": "forged"}},
        {"product_id": 999},
        {"options": {}},
        {"price": "0.01"},
        {"total": "0.01"},
        {"discount": "99.99"},
        {"currency": "USD"},
        {"customer_id": 999},
        {"user_id": 999},
        {"role": "admin"},
        {"provider_cost": "0.01"},
        {"provider_assignment": "forged-provider"},
        {"availability_state": "available"},
        {"direct_checkout_eligible": True},
        {"production_lead_time_days": 1},
        {"arbitrary": "value"},
    ],
)
def test_pricing_quote_endpoint_strictly_rejects_design_extras(extra_claim):
    db = build_session()
    owner = seed_user(db)
    design = seed_design(db, owner=owner, product=seed_product(db))
    adapter = RecordingProviderAdapter({})
    configure_pricing_endpoint_test_with_adapter(db, adapter, owner)
    persistence_before = persistence_snapshot(db)

    try:
        response = asyncio.run(
            post_pricing_quote(
                {
                    "item_type": "design",
                    "item_id": design.id,
                    "quantity": 1,
                    **extra_claim,
                }
            )
        )

        assert response.status_code == 400
        assert response.json() == {
            "detail": {
                "code": "frontend_pricing_claim_not_allowed",
                "message": "Extra frontend claims are not accepted for Design pricing.",
            }
        }
        assert persistence_snapshot(db) == persistence_before
        assert adapter.requests == []
        assert adapter.handoffs_by_key == {}
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("rejection", "code"),
    [
        ("template", "inactive_template"),
        ("product", "inactive"),
        ("configuration", "design_configuration_unavailable"),
        ("malformed_configuration", "design_configuration_unavailable"),
        ("retired_configuration", "design_configuration_unavailable"),
    ],
)
def test_pricing_quote_endpoint_rejects_unpriceable_persisted_design(
    rejection,
    code,
):
    db = build_session()
    owner = seed_user(db)
    product = seed_product(db)
    design = seed_design(db, owner=owner, product=product)
    if rejection == "template":
        design.template.is_active = False
    elif rejection == "product":
        product.is_active = False
    elif rejection == "malformed_configuration":
        design.customization_values = []
    elif rejection == "retired_configuration":
        design.template.template_fields[0].is_active = False
    else:
        design.customization_values = {"internal_unknown": "secret"}
    db.commit()
    adapter = RecordingProviderAdapter(
        {(CatalogItemType.DESIGN, design.id): available_fixture("12.00")}
    )
    configure_pricing_endpoint_test_with_adapter(db, adapter, owner)
    persistence_before = persistence_snapshot(db)

    try:
        response = asyncio.run(
            post_pricing_quote(
                {"item_type": "design", "item_id": design.id, "quantity": 1}
            )
        )

        assert_pricing_rejection(response, code)
        if "configuration" in rejection:
            assert response.json() == {
                "detail": {
                    "code": "design_configuration_unavailable",
                    "message": "Design configuration is unavailable.",
                }
            }
        assert persistence_snapshot(db) == persistence_before
        assert adapter.requests == []
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("fixture", "code"),
    [
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.TEMPORARILY_UNAVAILABLE,
                provider_cost=Decimal("12.00"),
                supports_requested_configuration=True,
                reason_code="temporarily_unavailable",
            ),
            "temporarily_unavailable",
        ),
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.MANUAL_QUOTE_REQUIRED,
                provider_cost=Decimal("12.00"),
                supports_requested_configuration=True,
                reason_code="manual_quote_required",
            ),
            "manual_quote_required",
        ),
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.OUTSOURCED_NOT_MVP_DIRECT,
                provider_cost=Decimal("12.00"),
                supports_requested_configuration=True,
                reason_code="outsourced_not_mvp_direct",
            ),
            "outsourced_not_mvp_direct",
        ),
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.UNSUPPORTED,
                provider_cost=Decimal("12.00"),
                supports_requested_configuration=True,
                reason_code="unsupported",
            ),
            "unsupported",
        ),
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.AVAILABLE,
                provider_cost=None,
                supports_requested_configuration=True,
                reason_code="provider_cost_missing",
            ),
            "provider_cost_missing",
        ),
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.AVAILABLE,
                provider_cost=Decimal("12.00"),
                supports_requested_configuration=False,
                reason_code="unsupported_configuration",
            ),
            "unsupported_configuration",
        ),
    ],
)
def test_pricing_quote_endpoint_rejects_design_provider_states_without_mutation(
    fixture,
    code,
):
    db = build_session()
    owner = seed_user(db)
    design = seed_design(db, owner=owner, product=seed_product(db))
    adapter = RecordingProviderAdapter({(CatalogItemType.DESIGN, design.id): fixture})
    configure_pricing_endpoint_test_with_adapter(db, adapter, owner)
    persistence_before = persistence_snapshot(db)

    try:
        response = asyncio.run(
            post_pricing_quote(
                {"item_type": "design", "item_id": design.id, "quantity": 1}
            )
        )

        assert_pricing_rejection(response, code)
        assert persistence_snapshot(db) == persistence_before
        assert adapter.handoffs_by_key == {}
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("quantity", "code"),
    [
        (0, "quantity_too_low"),
        (-1, "quantity_too_low"),
        (101, "quantity_too_high"),
        (1.5, "invalid_quantity"),
        (True, "invalid_quantity"),
    ],
)
def test_pricing_quote_endpoint_rejects_invalid_design_quantity(quantity, code):
    db = build_session()
    owner = seed_user(db)
    design = seed_design(db, owner=owner, product=seed_product(db))
    adapter = RecordingProviderAdapter({})
    configure_pricing_endpoint_test_with_adapter(db, adapter, owner)

    try:
        response = asyncio.run(
            post_pricing_quote(
                {"item_type": "design", "item_id": design.id, "quantity": quantity}
            )
        )

        assert_pricing_rejection(response, code)
        assert adapter.requests == []
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
    assert operation["security"] == [{"HTTPBearer": []}, {}]
    assert {"400", "401", "404"} <= set(operation["responses"])
    success_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert success_schema["discriminator"]["propertyName"] == "item_type"
    assert success_schema["discriminator"]["mapping"] == {
        "product": "#/components/schemas/ProductPricingQuoteResponse",
        "kit": "#/components/schemas/KitPricingQuoteResponse",
        "design": "#/components/schemas/DesignPricingQuoteResponse",
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
    assert (
        schema["components"]["schemas"]["DesignPricingQuoteRequest"][
            "additionalProperties"
        ]
        is False
    )
