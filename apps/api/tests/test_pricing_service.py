from decimal import Decimal

import pytest
from app.domain.provider_adapter import (
    AvailabilityState,
    CatalogItemType,
    LocalMockProviderAdapter,
    LocalProviderFixture,
)
from app.models.kit import Kit
from app.models.kit_item import KitItem
from app.models.product import Product
from app.services.pricing_service import (
    MAX_PRICING_QUANTITY,
    PathAPricingRequest,
    PathAPricingService,
    PricingItemType,
    PricingRejected,
)


def build_product(
    product_id: int = 1,
    base_price: str = "20.00",
    is_active: bool = True,
) -> Product:
    """Build a Product model for pricing service unit tests."""
    return Product(
        id=product_id,
        name="Emergency exit sign",
        description=None,
        category_id=1,
        base_price=Decimal(base_price),
        is_active=is_active,
    )


def build_kit(
    kit_id: int = 10,
    product: Product | None = None,
    item_quantity: int = 2,
) -> Kit:
    """Build a Kit model with one backend-owned required KitItem."""
    product = product or build_product()
    kit = Kit(
        id=kit_id,
        name="Emergency evacuation kit",
        description=None,
        is_active=True,
    )
    kit.kit_items = [
        KitItem(
            kit=kit,
            kit_id=kit.id,
            product=product,
            product_id=product.id,
            quantity=item_quantity,
        )
    ]
    return kit


def available_fixture(cost: str = "12.00") -> LocalProviderFixture:
    """Return a direct-checkout eligible local provider fixture."""
    return LocalProviderFixture(
        availability_state=AvailabilityState.AVAILABLE,
        provider_cost=Decimal(cost),
        supports_requested_configuration=True,
    )


def pricing_service(fixtures) -> PathAPricingService:
    """Build a pricing service backed by deterministic local fixtures."""
    return PathAPricingService(LocalMockProviderAdapter(fixtures))


def assert_rejected_code(callable_under_test, code: str) -> None:
    """Assert a pricing operation raises the expected stable rejection code."""
    with pytest.raises(PricingRejected) as exc_info:
        callable_under_test()

    assert exc_info.value.code == code


def test_product_pricing_contract_validates_backend_item_and_provider_cost_input():
    product = build_product(base_price="20.00")
    service = pricing_service(
        {(CatalogItemType.PRODUCT, product.id): available_fixture("12.00")}
    )

    result = service.validate_pricing_request(
        PathAPricingRequest(
            item_type=PricingItemType.PRODUCT,
            item=product,
            quantity=3,
        )
    )

    assert result.item_type is PricingItemType.PRODUCT
    assert result.item_id == product.id
    assert result.quantity == 3
    assert result.provider_cost_input_available is True
    assert result.provider_quote_reference == f"local-quote-product-{product.id}"
    assert not hasattr(result, "customer_unit_price")
    assert not hasattr(result, "customer_subtotal")
    assert not hasattr(result, "customer_total")


def test_kit_pricing_contract_validates_backend_owned_required_contents():
    product = build_product(product_id=1, base_price="20.00")
    kit = build_kit(kit_id=10, product=product, item_quantity=2)
    service = pricing_service(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("30.00"),
            (CatalogItemType.PRODUCT, product.id): available_fixture("12.00"),
        }
    )

    result = service.validate_pricing_request(
        PathAPricingRequest(
            item_type=PricingItemType.KIT,
            item=kit,
            quantity=3,
        )
    )

    assert result.item_type is PricingItemType.KIT
    assert result.item_id == kit.id
    assert result.quantity == 3
    assert result.provider_cost_input_available is True
    assert result.provider_quote_reference == f"local-quote-kit-{kit.id}"
    assert not hasattr(result, "customer_unit_price")
    assert not hasattr(result, "customer_subtotal")
    assert not hasattr(result, "customer_total")


def test_product_pricing_preview_uses_temporary_backend_base_price_rule():
    product = build_product(base_price="20.00")
    service = pricing_service(
        {(CatalogItemType.PRODUCT, product.id): available_fixture("12.00")}
    )

    result = service.preview_price(
        PathAPricingRequest(
            item_type=PricingItemType.PRODUCT,
            item=product,
            quantity=3,
        )
    )

    assert result.item_type is PricingItemType.PRODUCT
    assert result.item_id == product.id
    assert result.quantity == 3
    assert result.currency == "COP"
    assert result.customer_unit_price == Decimal("20.00")
    assert result.customer_subtotal == Decimal("60.00")
    assert result.customer_total == Decimal("60.00")
    assert result.pricing_rule == "temporary_product_base_price_v1"
    assert result.provider_quote_reference == f"local-quote-product-{product.id}"
    assert not hasattr(result, "provider_cost")
    assert not hasattr(result, "provider_cost_input")
    assert not hasattr(result, "provider_cost_total")


@pytest.mark.parametrize(
    "frontend_claims",
    [
        {"price": "0.01"},
        {"base_price": "0.01"},
        {"total": "0.01"},
        {"subtotal": "0.01"},
        {"discount": "99.99"},
        {"tax": "0.00"},
        {"fee": "0.00"},
        {"final_amount": "0.01"},
        {"provider_cost": "0.01"},
        {"provider_id": "forged-provider"},
        {"user_id": 999},
        {"role": "admin"},
        {"availability_state": "available"},
        {"direct_checkout_eligible": True},
        {"production_lead_time_days": 1},
    ],
)
def test_pricing_rejects_frontend_price_and_provider_truth_claims(frontend_claims):
    product = build_product()
    service = pricing_service(
        {(CatalogItemType.PRODUCT, product.id): available_fixture("12.00")}
    )

    assert_rejected_code(
        lambda: service.preview_price(
            PathAPricingRequest(
                item_type=PricingItemType.PRODUCT,
                item=product,
                quantity=1,
                frontend_claims=frontend_claims,
            )
        ),
        "frontend_pricing_claim_not_allowed",
    )


def test_pricing_rejects_inactive_product():
    product = build_product(is_active=False)
    service = pricing_service(
        {(CatalogItemType.PRODUCT, product.id): available_fixture("12.00")}
    )

    assert_rejected_code(
        lambda: service.preview_price(
            PathAPricingRequest(
                item_type=PricingItemType.PRODUCT,
                item=product,
                quantity=1,
            )
        ),
        "inactive",
    )


@pytest.mark.parametrize(
    ("availability_state", "reason_code"),
    [
        (AvailabilityState.TEMPORARILY_UNAVAILABLE, "temporarily_unavailable"),
        (AvailabilityState.MANUAL_QUOTE_REQUIRED, "manual_quote_required"),
        (AvailabilityState.OUTSOURCED_NOT_MVP_DIRECT, "outsourced_not_mvp_direct"),
    ],
)
def test_product_pricing_rejects_unavailable_manual_quote_and_outsourced_items(
    availability_state,
    reason_code,
):
    product = build_product()
    service = pricing_service(
        {
            (CatalogItemType.PRODUCT, product.id): LocalProviderFixture(
                availability_state=availability_state,
                provider_cost=Decimal("12.00"),
                supports_requested_configuration=True,
                reason_code=reason_code,
            )
        }
    )

    assert_rejected_code(
        lambda: service.preview_price(
            PathAPricingRequest(
                item_type=PricingItemType.PRODUCT,
                item=product,
                quantity=1,
            )
        ),
        reason_code,
    )


def test_kit_pricing_preview_is_explicitly_deferred_without_pricing_method():
    product = build_product()
    kit = build_kit(product=product)
    service = pricing_service({})

    assert_rejected_code(
        lambda: service.preview_price(
            PathAPricingRequest(
                item_type=PricingItemType.KIT,
                item=kit,
                quantity=1,
            )
        ),
        "kit_pricing_deferred",
    )


@pytest.mark.parametrize(
    ("availability_state", "reason_code"),
    [
        (AvailabilityState.TEMPORARILY_UNAVAILABLE, "temporarily_unavailable"),
        (AvailabilityState.MANUAL_QUOTE_REQUIRED, "manual_quote_required"),
        (AvailabilityState.OUTSOURCED_NOT_MVP_DIRECT, "outsourced_not_mvp_direct"),
    ],
)
def test_kit_pricing_contract_rejects_unavailable_manual_quote_and_outsourced_contents(
    availability_state,
    reason_code,
):
    product = build_product()
    kit = build_kit(product=product)
    service = pricing_service(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("30.00"),
            (CatalogItemType.PRODUCT, product.id): LocalProviderFixture(
                availability_state=availability_state,
                provider_cost=Decimal("12.00"),
                supports_requested_configuration=True,
                reason_code=reason_code,
            ),
        }
    )

    assert_rejected_code(
        lambda: service.validate_pricing_request(
            PathAPricingRequest(
                item_type=PricingItemType.KIT,
                item=kit,
                quantity=1,
            )
        ),
        reason_code,
    )


def test_pricing_rejects_invalid_configuration_options():
    product = build_product()
    service = pricing_service(
        {(CatalogItemType.PRODUCT, product.id): available_fixture("12.00")}
    )

    assert_rejected_code(
        lambda: service.preview_price(
            PathAPricingRequest(
                item_type=PricingItemType.PRODUCT,
                item=product,
                quantity=1,
                options={"material": "forged-acrylic"},
            )
        ),
        "invalid_configuration",
    )


@pytest.mark.parametrize(
    ("quantity", "code"),
    [
        (0, "quantity_too_low"),
        (-1, "quantity_too_low"),
        (MAX_PRICING_QUANTITY + 1, "quantity_too_high"),
        (1.5, "invalid_quantity"),
        (True, "invalid_quantity"),
    ],
)
def test_pricing_rejects_invalid_or_abusive_quantities(quantity, code):
    product = build_product()
    service = pricing_service(
        {(CatalogItemType.PRODUCT, product.id): available_fixture("12.00")}
    )

    assert_rejected_code(
        lambda: service.preview_price(
            PathAPricingRequest(
                item_type=PricingItemType.PRODUCT,
                item=product,
                quantity=quantity,
            )
        ),
        code,
    )


def test_design_pricing_contract_boundary_is_defined_but_deferred():
    service = pricing_service({})

    assert_rejected_code(
        lambda: service.preview_price(
            PathAPricingRequest(
                item_type=PricingItemType.DESIGN,
                item=object(),
                quantity=1,
            )
        ),
        "design_pricing_contract_only",
    )


def test_product_pricing_preview_requires_provider_cost_input_without_exposing_it():
    product = build_product()
    service = pricing_service(
        {
            (CatalogItemType.PRODUCT, product.id): LocalProviderFixture(
                availability_state=AvailabilityState.AVAILABLE,
                provider_cost=None,
                supports_requested_configuration=True,
                reason_code="provider_cost_missing",
            )
        }
    )

    assert_rejected_code(
        lambda: service.preview_price(
            PathAPricingRequest(
                item_type=PricingItemType.PRODUCT,
                item=product,
                quantity=1,
            )
        ),
        "provider_cost_missing",
    )
