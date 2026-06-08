from decimal import Decimal

import pytest
from app.core.database import Base
from app.domain.provider_adapter import (
    AvailabilityState,
    CatalogItemType,
    LocalMockProviderAdapter,
    LocalProviderFixture,
)
from app.domain.order_lifecycle import OrderStatus
from app.models.category import Category
from app.models.kit import Kit
from app.models.kit_item import KitItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User
from app.repositories.kit_repository import KitRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.checkout import (
    CheckoutEligibilityRequest,
    CheckoutTermsAcknowledgement,
)
from app.services.checkout_service import (
    DEFAULT_TERMS_POLICY_VERSION,
    CheckoutEligibilityService,
    CheckoutRejected,
)
from app.services.pricing_service import PathAPricingService, PricingItemType
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for checkout tests."""
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


def seed_product(
    db,
    *,
    base_price: str = "20.00",
    is_active: bool = True,
) -> Product:
    """Persist one Product for checkout eligibility tests."""
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


def seed_kit(db, product: Product) -> Kit:
    """Persist one Kit with a required Product for checkout tests."""
    kit = Kit(name="Evacuation kit", description=None, is_active=True)
    db.add(kit)
    db.flush()
    db.add(KitItem(kit=kit, product=product, quantity=2))
    db.commit()
    db.refresh(kit)
    return kit


def available_fixture(cost: str = "12.00") -> LocalProviderFixture:
    """Return a direct-checkout eligible local provider fixture."""
    return LocalProviderFixture(
        availability_state=AvailabilityState.AVAILABLE,
        provider_cost=Decimal(cost),
        supports_requested_configuration=True,
    )


def fixture_with_state(
    state: AvailabilityState,
    *,
    reason_code: str,
) -> LocalProviderFixture:
    """Return a local provider fixture in a non-direct-checkout state."""
    return LocalProviderFixture(
        availability_state=state,
        provider_cost=Decimal("12.00"),
        supports_requested_configuration=True,
        reason_code=reason_code,
    )


def terms(version: str = DEFAULT_TERMS_POLICY_VERSION):
    """Return accepted checkout terms acknowledgement for tests."""
    return CheckoutTermsAcknowledgement(accepted=True, policy_version=version)


def checkout_request(product: Product, **overrides) -> CheckoutEligibilityRequest:
    """Build a product checkout eligibility request."""
    values = {
        "item_type": PricingItemType.PRODUCT,
        "item_id": product.id,
        "quantity": 2,
        "terms_acknowledgement": terms(),
    }
    values.update(overrides)
    return CheckoutEligibilityRequest(**values)


def checkout_service(db, provider_adapter) -> CheckoutEligibilityService:
    """Build a checkout eligibility service with repository dependencies."""
    return CheckoutEligibilityService(
        ProductRepository(db),
        KitRepository(db),
        PathAPricingService(provider_adapter),
    )


def table_count(db, model) -> int:
    """Return the number of persisted rows for a model."""
    return db.scalar(select(func.count()).select_from(model))


def assert_checkout_rejected(
    service: CheckoutEligibilityService,
    request: CheckoutEligibilityRequest,
    code: str,
) -> None:
    """Assert checkout validation raises the expected stable rejection code."""
    with pytest.raises(CheckoutRejected) as exc_info:
        service.validate_checkout(request)

    assert exc_info.value.code == code


def assert_no_checkout_side_effects(db, provider_adapter) -> None:
    """Assert rejected checkout did not create order or provider records."""
    assert table_count(db, Order) == 0
    assert table_count(db, OrderItem) == 0
    assert provider_adapter.handoffs_by_key == {}


def test_checkout_eligibility_returns_validated_product_state():
    db = build_session()
    try:
        product = seed_product(db, base_price="20.00")
        provider_adapter = LocalMockProviderAdapter(
            {(CatalogItemType.PRODUCT, product.id): available_fixture("12.00")}
        )
        service = checkout_service(db, provider_adapter)

        result = service.validate_checkout(checkout_request(product, quantity=3))

        assert result.item_type is PricingItemType.PRODUCT
        assert result.item_id == product.id
        assert result.quantity == 3
        assert result.selected_options == {}
        assert result.currency == "COP"
        assert result.customer_unit_price == Decimal("20.00")
        assert result.customer_subtotal == Decimal("60.00")
        assert result.preview_total == Decimal("60.00")
        assert result.pricing_rule == "temporary_product_base_price_v1"
        assert result.provider_quote_reference == f"local-quote-product-{product.id}"
        assert result.assigned_provider_id == "local-provider"
        assert result.terms_policy_version == DEFAULT_TERMS_POLICY_VERSION
        assert "provider_cost" not in result.model_dump()
        assert provider_adapter.handoffs_by_key == {}
    finally:
        db.close()


def test_checkout_rejects_frontend_price_tampering_without_mutation():
    db = build_session()
    try:
        product = seed_product(db)
        provider_adapter = LocalMockProviderAdapter(
            {(CatalogItemType.PRODUCT, product.id): available_fixture()}
        )
        service = checkout_service(db, provider_adapter)
        request = checkout_request(
            product,
            price="0.01",
            total="0.01",
            checkout_total="0.01",
        )

        assert_checkout_rejected(
            service,
            request,
            "frontend_pricing_claim_not_allowed",
        )
        assert_no_checkout_side_effects(db, provider_adapter)
    finally:
        db.close()


def test_checkout_rejects_frontend_provider_truth_claims_without_mutation():
    db = build_session()
    try:
        product = seed_product(db)
        provider_adapter = LocalMockProviderAdapter(
            {(CatalogItemType.PRODUCT, product.id): available_fixture()}
        )
        service = checkout_service(db, provider_adapter)
        request = checkout_request(
            product,
            provider_cost="0.01",
            availability_state="available",
            direct_checkout_eligible=True,
            production_lead_time_days=1,
        )

        assert_checkout_rejected(
            service,
            request,
            "frontend_pricing_claim_not_allowed",
        )
        assert_no_checkout_side_effects(db, provider_adapter)
    finally:
        db.close()


def test_checkout_rejects_missing_terms_acknowledgement_without_mutation():
    db = build_session()
    try:
        product = seed_product(db)
        provider_adapter = LocalMockProviderAdapter(
            {(CatalogItemType.PRODUCT, product.id): available_fixture()}
        )
        service = checkout_service(db, provider_adapter)
        request = checkout_request(product, terms_acknowledgement=None)

        assert_checkout_rejected(
            service,
            request,
            "terms_acknowledgement_required",
        )
        assert_no_checkout_side_effects(db, provider_adapter)
    finally:
        db.close()


def test_checkout_rejects_forged_terms_policy_version_without_mutation():
    db = build_session()
    try:
        product = seed_product(db)
        provider_adapter = LocalMockProviderAdapter(
            {(CatalogItemType.PRODUCT, product.id): available_fixture()}
        )
        service = checkout_service(db, provider_adapter)
        request = checkout_request(product, terms_acknowledgement=terms("forged-v0"))

        assert_checkout_rejected(service, request, "terms_policy_version_mismatch")
        assert_no_checkout_side_effects(db, provider_adapter)
    finally:
        db.close()


@pytest.mark.parametrize(
    ("state", "reason_code"),
    [
        (AvailabilityState.TEMPORARILY_UNAVAILABLE, "temporarily_unavailable"),
        (AvailabilityState.MANUAL_QUOTE_REQUIRED, "manual_quote_required"),
        (AvailabilityState.OUTSOURCED_NOT_MVP_DIRECT, "outsourced_not_mvp_direct"),
    ],
)
def test_checkout_rejects_unavailable_manual_quote_or_outsourced_items(
    state,
    reason_code,
):
    db = build_session()
    try:
        product = seed_product(db)
        provider_adapter = LocalMockProviderAdapter(
            {
                (CatalogItemType.PRODUCT, product.id): fixture_with_state(
                    state,
                    reason_code=reason_code,
                )
            }
        )
        service = checkout_service(db, provider_adapter)

        assert_checkout_rejected(service, checkout_request(product), reason_code)
        assert_no_checkout_side_effects(db, provider_adapter)
    finally:
        db.close()


def test_checkout_rejects_inactive_product_without_mutation():
    db = build_session()
    try:
        product = seed_product(db, is_active=False)
        provider_adapter = LocalMockProviderAdapter(
            {(CatalogItemType.PRODUCT, product.id): available_fixture()}
        )
        service = checkout_service(db, provider_adapter)

        assert_checkout_rejected(service, checkout_request(product), "inactive")
        assert_no_checkout_side_effects(db, provider_adapter)
    finally:
        db.close()


def test_checkout_rejects_stale_catalog_item_without_mutation():
    db = build_session()
    try:
        provider_adapter = LocalMockProviderAdapter({})
        service = checkout_service(db, provider_adapter)
        request = CheckoutEligibilityRequest(
            item_type=PricingItemType.PRODUCT,
            item_id=999,
            quantity=1,
            terms_acknowledgement=terms(),
        )

        assert_checkout_rejected(service, request, "catalog_item_not_found")
        assert_no_checkout_side_effects(db, provider_adapter)
    finally:
        db.close()


def test_checkout_rejects_invalid_configuration_without_mutation():
    db = build_session()
    try:
        product = seed_product(db)
        provider_adapter = LocalMockProviderAdapter(
            {(CatalogItemType.PRODUCT, product.id): available_fixture()}
        )
        service = checkout_service(db, provider_adapter)
        request = checkout_request(product, options={"finish": "forged"})

        assert_checkout_rejected(service, request, "invalid_configuration")
        assert_no_checkout_side_effects(db, provider_adapter)
    finally:
        db.close()


def test_checkout_rejects_kit_until_backend_pricing_preview_exists():
    db = build_session()
    try:
        product = seed_product(db)
        kit = seed_kit(db, product)
        provider_adapter = LocalMockProviderAdapter(
            {
                (CatalogItemType.KIT, kit.id): available_fixture("30.00"),
                (CatalogItemType.PRODUCT, product.id): available_fixture("12.00"),
            }
        )
        service = checkout_service(db, provider_adapter)
        request = CheckoutEligibilityRequest(
            item_type=PricingItemType.KIT,
            item_id=kit.id,
            quantity=1,
            terms_acknowledgement=terms(),
        )

        assert_checkout_rejected(service, request, "kit_pricing_deferred")
        assert_no_checkout_side_effects(db, provider_adapter)
    finally:
        db.close()


def test_rejected_checkout_does_not_mutate_existing_order_records():
    db = build_session()
    try:
        product = seed_product(db)
        customer = User(email="buyer@example.com", full_name="Test Buyer")
        db.add(customer)
        db.flush()
        existing_order = Order(
            customer_id=customer.id,
            status=OrderStatus.DRAFT.value,
            subtotal_amount=Decimal("1.00"),
            total_amount=Decimal("1.00"),
            currency="COP",
        )
        db.add(existing_order)
        db.commit()
        provider_adapter = LocalMockProviderAdapter(
            {(CatalogItemType.PRODUCT, product.id): available_fixture()}
        )
        service = checkout_service(db, provider_adapter)
        request = checkout_request(product, terms_acknowledgement=None)

        assert_checkout_rejected(
            service,
            request,
            "terms_acknowledgement_required",
        )

        assert table_count(db, Order) == 1
        assert table_count(db, OrderItem) == 0
        assert db.get(Order, existing_order.id).status == OrderStatus.DRAFT.value
        assert provider_adapter.handoffs_by_key == {}
    finally:
        db.close()
