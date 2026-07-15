from decimal import Decimal

import pytest
from app.domain.provider_adapter import (
    AvailabilityState,
    CatalogItemType,
    EligibilityResult,
    EligibilityState,
    LocalMockProviderAdapter,
    LocalProviderFixture,
    ProviderItemRequest,
)
from app.models.design import Design
from app.models.kit import Kit
from app.models.kit_item import KitItem
from app.models.product import Product
from app.models.template import Template
from app.services.design_validation_service import DesignValidationError
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


def build_multi_product_kit() -> tuple[Kit, Product, Product]:
    """Build a Kit whose persisted item ids define a non-product ordering."""
    first_product = build_product(product_id=1, base_price="20.00")
    first_product.name = "Exit route sign"
    second_product = build_product(product_id=2, base_price="10.00")
    second_product.name = "Assembly point sign"
    kit = Kit(
        id=10,
        name="Emergency evacuation kit",
        description=None,
        is_active=True,
    )
    kit.kit_items = [
        KitItem(
            id=30,
            kit=kit,
            kit_id=kit.id,
            product=second_product,
            product_id=second_product.id,
            quantity=1,
        ),
        KitItem(
            id=10,
            kit=kit,
            kit_id=kit.id,
            product=first_product,
            product_id=first_product.id,
            quantity=2,
        ),
        KitItem(
            id=20,
            kit=kit,
            kit_id=kit.id,
            product=first_product,
            product_id=first_product.id,
            quantity=1,
        ),
    ]
    return kit, first_product, second_product


class RecordingProviderAdapter(LocalMockProviderAdapter):
    """Record every provider item request while retaining local behavior."""

    def __init__(self, fixtures) -> None:
        """Store fixtures and initialize request recording."""
        super().__init__(fixtures)
        self.requests: list[tuple[str, ProviderItemRequest]] = []

    def check_availability(self, request):
        """Record one availability request."""
        self.requests.append(("availability", request))
        return super().check_availability(request)

    def quote_pricing(self, request):
        """Record one pricing request."""
        self.requests.append(("pricing", request))
        return super().quote_pricing(request)

    def check_direct_checkout_eligibility(self, request):
        """Record one direct-checkout request."""
        self.requests.append(("eligibility", request))
        return super().check_direct_checkout_eligibility(request)

    def estimate_lead_time(self, request):
        """Record one lead-time request."""
        self.requests.append(("lead_time", request))
        return super().estimate_lead_time(request)


class IneligibleProviderAdapter(LocalMockProviderAdapter):
    """Return explicit provider ineligibility for one catalog item type."""

    def __init__(self, fixtures, blocked_item_type: CatalogItemType) -> None:
        """Store fixtures and the item type rejected by eligibility checks."""
        super().__init__(fixtures)
        self.blocked_item_type = blocked_item_type

    def check_direct_checkout_eligibility(self, request):
        """Reject the configured item type while preserving other fixtures."""
        if request.item_type is self.blocked_item_type:
            return EligibilityResult(
                state=EligibilityState.NOT_ELIGIBLE,
                assigned_provider_id=request.assigned_provider_id,
                reason_code="provider_not_eligible",
            )
        return super().check_direct_checkout_eligibility(request)


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

    result = service.preview_quote(
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
        lambda: service.preview_quote(
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
        lambda: service.preview_quote(
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
        (AvailabilityState.UNSUPPORTED, "unsupported"),
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
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.PRODUCT,
                item=product,
                quantity=1,
            )
        ),
        reason_code,
    )


def test_kit_pricing_preview_uses_backend_contents_in_stable_item_order():
    kit, first_product, second_product = build_multi_product_kit()
    service = pricing_service(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("30.00"),
            (CatalogItemType.PRODUCT, first_product.id): available_fixture("12.00"),
            (CatalogItemType.PRODUCT, second_product.id): available_fixture("6.00"),
        }
    )

    request = PathAPricingRequest(
        item_type=PricingItemType.KIT,
        item=kit,
        quantity=3,
    )
    result = service.preview_quote(request)
    repeated_result = service.preview_quote(request)

    assert result == repeated_result
    assert result.item_type is PricingItemType.KIT
    assert result.item_id == kit.id
    assert result.quantity == 3
    assert result.currency == "COP"
    assert result.customer_unit_price == Decimal("70.00")
    assert result.customer_subtotal == Decimal("210.00")
    assert result.customer_total == Decimal("210.00")
    assert result.pricing_rule == "temporary_kit_contents_base_price_v1"
    assert result.provider_quote_reference == f"local-quote-kit-{kit.id}"
    assert [line.product_id for line in result.lines] == [1, 1, 2]
    assert [line.quantity_per_kit for line in result.lines] == [2, 1, 1]
    assert [line.total_quantity for line in result.lines] == [6, 3, 3]
    assert [line.customer_unit_price for line in result.lines] == [
        Decimal("20.00"),
        Decimal("20.00"),
        Decimal("10.00"),
    ]
    assert [line.customer_subtotal for line in result.lines] == [
        Decimal("120.00"),
        Decimal("60.00"),
        Decimal("30.00"),
    ]
    assert not hasattr(result, "provider_cost")


def test_kit_pricing_uses_requested_and_effective_provider_quantities():
    kit, first_product, second_product = build_multi_product_kit()
    adapter = RecordingProviderAdapter(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("30.00"),
            (CatalogItemType.PRODUCT, first_product.id): available_fixture("12.00"),
            (CatalogItemType.PRODUCT, second_product.id): available_fixture("6.00"),
        }
    )
    service = PathAPricingService(adapter)

    service.preview_quote(
        PathAPricingRequest(
            item_type=PricingItemType.KIT,
            item=kit,
            quantity=3,
        )
    )

    kit_requests = [
        request
        for _, request in adapter.requests
        if request.item_type is CatalogItemType.KIT
    ]
    product_requests = [
        request
        for _, request in adapter.requests
        if request.item_type is CatalogItemType.PRODUCT
    ]
    assert kit_requests
    assert {request.quantity for request in kit_requests} == {3}
    assert {(request.item_id, request.quantity) for request in product_requests} == {
        (first_product.id, 3),
        (first_product.id, 6),
        (second_product.id, 3),
    }


@pytest.mark.parametrize("quantity", [1, MAX_PRICING_QUANTITY])
def test_kit_pricing_accepts_requested_quantity_boundaries(quantity):
    product = build_product()
    kit = build_kit(product=product, item_quantity=1)
    service = pricing_service(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("30.00"),
            (CatalogItemType.PRODUCT, product.id): available_fixture("12.00"),
        }
    )

    result = service.preview_quote(
        PathAPricingRequest(
            item_type=PricingItemType.KIT,
            item=kit,
            quantity=quantity,
        )
    )

    assert result.quantity == quantity
    assert result.lines[0].total_quantity == quantity


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
def test_kit_pricing_rejects_invalid_requested_quantities_without_provider_calls(
    quantity,
    code,
):
    product = build_product()
    kit = build_kit(product=product)
    adapter = RecordingProviderAdapter({})
    service = PathAPricingService(adapter)

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.KIT,
                item=kit,
                quantity=quantity,
            )
        ),
        code,
    )
    assert adapter.requests == []


@pytest.mark.parametrize("item_quantity", [0, -1, True, 1.5])
def test_kit_pricing_rejects_invalid_persisted_item_quantity(item_quantity):
    product = build_product()
    kit = build_kit(product=product, item_quantity=item_quantity)
    service = pricing_service({})

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.KIT,
                item=kit,
                quantity=1,
            )
        ),
        "invalid_kit_configuration",
    )


def test_kit_pricing_rejects_effective_product_quantity_above_limit():
    product = build_product()
    kit = build_kit(product=product, item_quantity=2)
    service = pricing_service({})

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.KIT,
                item=kit,
                quantity=MAX_PRICING_QUANTITY,
            )
        ),
        "quantity_too_high",
    )


@pytest.mark.parametrize(
    ("kit", "code"),
    [
        (Kit(id=10, name="Inactive", description=None, is_active=False), "inactive"),
        (Kit(id=11, name="Empty", description=None, is_active=True), "empty_kit"),
    ],
)
def test_kit_pricing_rejects_inactive_or_empty_kit(kit, code):
    kit.kit_items = []
    service = pricing_service({})

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.KIT,
                item=kit,
                quantity=1,
            )
        ),
        code,
    )


def test_kit_pricing_aggregates_inactive_required_content():
    inactive_product = build_product(is_active=False)
    kit = build_kit(product=inactive_product)
    adapter = RecordingProviderAdapter({})
    service = PathAPricingService(adapter)

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.KIT,
                item=kit,
                quantity=1,
            )
        ),
        "kit_contents_unavailable",
    )
    assert adapter.requests == []


@pytest.mark.parametrize(
    "active_fixture",
    [
        available_fixture("12.00"),
        LocalProviderFixture(
            availability_state=AvailabilityState.MANUAL_QUOTE_REQUIRED,
            provider_cost=Decimal("12.00"),
            supports_requested_configuration=True,
            reason_code="manual_quote_required",
        ),
    ],
)
def test_kit_pricing_rejects_mixed_inactive_content_before_provider_checks(
    active_fixture,
):
    active_product = build_product(product_id=1)
    inactive_product = build_product(product_id=2, is_active=False)
    kit = build_kit(product=active_product, item_quantity=1)
    kit.kit_items.append(
        KitItem(
            id=2,
            kit=kit,
            kit_id=kit.id,
            product=inactive_product,
            product_id=inactive_product.id,
            quantity=1,
        )
    )
    adapter = RecordingProviderAdapter(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("30.00"),
            (CatalogItemType.PRODUCT, active_product.id): active_fixture,
        }
    )
    service = PathAPricingService(adapter)

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.KIT,
                item=kit,
                quantity=1,
            )
        ),
        "kit_contents_unavailable",
    )
    assert adapter.requests == []


@pytest.mark.parametrize(
    ("availability_state", "reason_code"),
    [
        (AvailabilityState.TEMPORARILY_UNAVAILABLE, "temporarily_unavailable"),
        (AvailabilityState.MANUAL_QUOTE_REQUIRED, "manual_quote_required"),
        (AvailabilityState.OUTSOURCED_NOT_MVP_DIRECT, "outsourced_not_mvp_direct"),
        (AvailabilityState.UNSUPPORTED, "unsupported"),
    ],
)
def test_kit_pricing_rejects_kit_level_provider_states(
    availability_state,
    reason_code,
):
    product = build_product()
    kit = build_kit(product=product)
    service = pricing_service(
        {
            (CatalogItemType.KIT, kit.id): LocalProviderFixture(
                availability_state=availability_state,
                provider_cost=Decimal("30.00"),
                supports_requested_configuration=True,
                reason_code=reason_code,
            ),
            (CatalogItemType.PRODUCT, product.id): available_fixture("12.00"),
        }
    )

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.KIT,
                item=kit,
                quantity=1,
            )
        ),
        reason_code,
    )


@pytest.mark.parametrize(
    "missing_cost_item_type", [CatalogItemType.KIT, CatalogItemType.PRODUCT]
)
def test_kit_pricing_requires_kit_and_product_provider_cost(missing_cost_item_type):
    product = build_product()
    kit = build_kit(product=product)
    fixtures = {
        (CatalogItemType.KIT, kit.id): available_fixture("30.00"),
        (CatalogItemType.PRODUCT, product.id): available_fixture("12.00"),
    }
    missing_item_id = (
        kit.id if missing_cost_item_type is CatalogItemType.KIT else product.id
    )
    fixtures[(missing_cost_item_type, missing_item_id)] = LocalProviderFixture(
        availability_state=AvailabilityState.AVAILABLE,
        provider_cost=None,
        supports_requested_configuration=True,
        reason_code="provider_cost_missing",
    )
    service = pricing_service(fixtures)

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.KIT,
                item=kit,
                quantity=1,
            )
        ),
        "provider_cost_missing",
    )


@pytest.mark.parametrize(
    "item_type",
    [CatalogItemType.KIT, CatalogItemType.PRODUCT],
)
def test_kit_pricing_rejects_unsupported_provider_configuration(item_type):
    product = build_product()
    kit = build_kit(product=product)
    fixtures = {
        (CatalogItemType.KIT, kit.id): available_fixture("30.00"),
        (CatalogItemType.PRODUCT, product.id): available_fixture("12.00"),
    }
    item_id = kit.id if item_type is CatalogItemType.KIT else product.id
    fixtures[(item_type, item_id)] = LocalProviderFixture(
        availability_state=AvailabilityState.AVAILABLE,
        provider_cost=Decimal("12.00"),
        supports_requested_configuration=False,
        reason_code="unsupported_configuration",
    )
    service = pricing_service(fixtures)

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.KIT,
                item=kit,
                quantity=1,
            )
        ),
        "unsupported_configuration",
    )


def test_kit_pricing_accepts_made_to_order_provider_state():
    product = build_product()
    kit = build_kit(product=product)
    made_to_order_fixture = LocalProviderFixture(
        availability_state=AvailabilityState.MADE_TO_ORDER_PARAMETRIZABLE,
        provider_cost=Decimal("12.00"),
        supports_requested_configuration=True,
    )
    service = pricing_service(
        {
            (CatalogItemType.KIT, kit.id): made_to_order_fixture,
            (CatalogItemType.PRODUCT, product.id): made_to_order_fixture,
        }
    )

    result = service.preview_quote(
        PathAPricingRequest(
            item_type=PricingItemType.KIT,
            item=kit,
            quantity=1,
        )
    )

    assert result.customer_total == Decimal("40.00")


@pytest.mark.parametrize(
    "blocked_item_type",
    [CatalogItemType.KIT, CatalogItemType.PRODUCT],
)
def test_kit_pricing_rejects_explicit_provider_ineligibility(blocked_item_type):
    product = build_product()
    kit = build_kit(product=product)
    adapter = IneligibleProviderAdapter(
        {
            (CatalogItemType.KIT, kit.id): available_fixture("30.00"),
            (CatalogItemType.PRODUCT, product.id): available_fixture("12.00"),
        },
        blocked_item_type,
    )
    service = PathAPricingService(adapter)

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.KIT,
                item=kit,
                quantity=1,
            )
        ),
        "provider_not_eligible",
    )


@pytest.mark.parametrize(
    "frontend_claims",
    [
        {"contents": []},
        {"kit_items": []},
        {"quantity_per_kit": 999},
        {"product_id": 999},
        {"base_price": "0.01"},
        {"customer_subtotal": "0.01"},
        {"preview_total": "0.01"},
        {"currency": "USD"},
        {"discount": "99.99"},
        {"tax": "0.00"},
        {"fee": "0.00"},
        {"arbitrary": "value"},
        {"customer_id": 999},
        {"role": "admin"},
        {"provider_cost": "0.01"},
        {"provider_id": "forged-provider"},
        {"availability_state": "available"},
        {"direct_checkout_eligible": True},
        {"production_lead_time_days": 1},
    ],
)
def test_kit_pricing_rejects_every_extra_frontend_claim(frontend_claims):
    product = build_product()
    kit = build_kit(product=product)
    service = pricing_service({})

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.KIT,
                item=kit,
                quantity=1,
                frontend_claims=frontend_claims,
            )
        ),
        "frontend_pricing_claim_not_allowed",
    )


@pytest.mark.parametrize(
    ("availability_state", "reason_code"),
    [
        (AvailabilityState.TEMPORARILY_UNAVAILABLE, "temporarily_unavailable"),
        (AvailabilityState.MANUAL_QUOTE_REQUIRED, "manual_quote_required"),
        (AvailabilityState.OUTSOURCED_NOT_MVP_DIRECT, "outsourced_not_mvp_direct"),
        (AvailabilityState.UNSUPPORTED, "unsupported"),
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
        lambda: service.preview_quote(
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
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.PRODUCT,
                item=product,
                quantity=quantity,
            )
        ),
        code,
    )


def test_design_pricing_uses_product_base_price_and_persisted_provider_options():
    product = build_product(base_price="25.00")
    template = Template(
        id=3,
        product=product,
        name="Emergency exit template",
        description=None,
        is_active=True,
    )
    design = Design(
        id=7,
        customer_id=11,
        template_id=template.id,
        template=template,
        customization_values={"legend": "Exit", "width_cm": 30},
    )
    adapter = RecordingProviderAdapter(
        {(CatalogItemType.DESIGN, design.id): available_fixture("15.00")}
    )

    class AcceptingValidationService:
        def validate_customization(self, template_id, customization_values):
            assert template_id == template.id
            return dict(customization_values)

    service = PathAPricingService(
        adapter,
        design_validation_service=AcceptingValidationService(),
    )
    request = PathAPricingRequest(
        item_type=PricingItemType.DESIGN,
        item=design,
        quantity=3,
    )

    result = service.preview_quote(request)
    repeated_result = service.preview_quote(request)

    assert result == repeated_result
    assert result.item_type is PricingItemType.DESIGN
    assert result.item_id == design.id
    assert result.customer_unit_price == Decimal("25.00")
    assert result.customer_subtotal == Decimal("75.00")
    assert result.customer_total == Decimal("75.00")
    assert result.pricing_rule == "temporary_design_product_base_price_v1"
    assert result.provider_quote_reference == "local-quote-design-7"
    assert adapter.requests
    assert all(
        provider_request.item_type is CatalogItemType.DESIGN
        and provider_request.item_id == design.id
        and provider_request.quantity == 3
        and provider_request.options == design.customization_values
        for _, provider_request in adapter.requests
    )


@pytest.mark.parametrize("quantity", [1, MAX_PRICING_QUANTITY])
def test_design_pricing_accepts_quantity_boundaries(quantity):
    product = build_product(base_price="25.00")
    template = Template(
        id=3,
        product=product,
        name="Emergency exit template",
        description=None,
        is_active=True,
    )
    design = Design(
        id=7,
        customer_id=11,
        template_id=template.id,
        template=template,
        customization_values={"legend": "Exit"},
    )

    class AcceptingValidationService:
        def validate_customization(self, template_id, customization_values):
            return dict(customization_values)

    service = PathAPricingService(
        LocalMockProviderAdapter(
            {(CatalogItemType.DESIGN, design.id): available_fixture("15.00")}
        ),
        design_validation_service=AcceptingValidationService(),
    )

    result = service.preview_quote(
        PathAPricingRequest(
            item_type=PricingItemType.DESIGN,
            item=design,
            quantity=quantity,
        )
    )

    assert result.quantity == quantity
    assert result.customer_total == Decimal("25.00") * quantity


@pytest.mark.parametrize(
    ("template_active", "product_active", "code"),
    [
        (False, True, "inactive_template"),
        (True, False, "inactive"),
    ],
)
def test_design_pricing_rejects_inactive_anchor_before_provider_calls(
    template_active,
    product_active,
    code,
):
    product = build_product(is_active=product_active)
    design = Design(
        id=7,
        customer_id=11,
        template_id=3,
        template=Template(
            id=3,
            product=product,
            name="Template",
            description=None,
            is_active=template_active,
        ),
        customization_values={"legend": "Exit"},
    )
    adapter = RecordingProviderAdapter({})
    service = PathAPricingService(adapter, design_validation_service=object())

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.DESIGN,
                item=design,
                quantity=1,
            )
        ),
        code,
    )
    assert adapter.requests == []


def test_design_pricing_hides_invalid_persisted_configuration():
    product = build_product()
    design = Design(
        id=7,
        customer_id=11,
        template_id=3,
        template=Template(
            id=3,
            product=product,
            name="Template",
            description=None,
            is_active=True,
        ),
        customization_values={"forged": "value"},
    )

    class RejectingValidationService:
        def validate_customization(self, template_id, customization_values):
            raise DesignValidationError("unknown_template_field", "internal detail")

    adapter = RecordingProviderAdapter({})
    service = PathAPricingService(
        adapter,
        design_validation_service=RejectingValidationService(),
    )

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.DESIGN,
                item=design,
                quantity=1,
            )
        ),
        "design_configuration_unavailable",
    )
    assert adapter.requests == []


@pytest.mark.parametrize(
    ("fixture", "code"),
    [
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.TEMPORARILY_UNAVAILABLE,
                provider_cost=Decimal("15.00"),
                supports_requested_configuration=True,
                reason_code="temporarily_unavailable",
            ),
            "temporarily_unavailable",
        ),
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.MANUAL_QUOTE_REQUIRED,
                provider_cost=Decimal("15.00"),
                supports_requested_configuration=True,
                reason_code="manual_quote_required",
            ),
            "manual_quote_required",
        ),
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.OUTSOURCED_NOT_MVP_DIRECT,
                provider_cost=Decimal("15.00"),
                supports_requested_configuration=True,
                reason_code="outsourced_not_mvp_direct",
            ),
            "outsourced_not_mvp_direct",
        ),
        (
            LocalProviderFixture(
                availability_state=AvailabilityState.UNSUPPORTED,
                provider_cost=Decimal("15.00"),
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
                provider_cost=Decimal("15.00"),
                supports_requested_configuration=False,
                reason_code="unsupported_configuration",
            ),
            "unsupported_configuration",
        ),
    ],
)
def test_design_pricing_rejects_provider_state_or_missing_cost(fixture, code):
    product = build_product()
    design = Design(
        id=7,
        customer_id=11,
        template_id=3,
        template=Template(
            id=3,
            product=product,
            name="Template",
            description=None,
            is_active=True,
        ),
        customization_values={"legend": "Exit"},
    )

    class AcceptingValidationService:
        def validate_customization(self, template_id, customization_values):
            return dict(customization_values)

    service = PathAPricingService(
        LocalMockProviderAdapter({(CatalogItemType.DESIGN, design.id): fixture}),
        design_validation_service=AcceptingValidationService(),
    )

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.DESIGN,
                item=design,
                quantity=1,
            )
        ),
        code,
    )


def test_design_pricing_rejects_explicit_provider_ineligibility():
    product = build_product()
    design = Design(
        id=7,
        customer_id=11,
        template_id=3,
        template=Template(
            id=3,
            product=product,
            name="Template",
            description=None,
            is_active=True,
        ),
        customization_values={"legend": "Exit"},
    )

    class AcceptingValidationService:
        def validate_customization(self, template_id, customization_values):
            return dict(customization_values)

    service = PathAPricingService(
        IneligibleProviderAdapter(
            {(CatalogItemType.DESIGN, design.id): available_fixture("15.00")},
            CatalogItemType.DESIGN,
        ),
        design_validation_service=AcceptingValidationService(),
    )

    assert_rejected_code(
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.DESIGN,
                item=design,
                quantity=1,
            )
        ),
        "provider_not_eligible",
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
        lambda: service.preview_quote(
            PathAPricingRequest(
                item_type=PricingItemType.PRODUCT,
                item=product,
                quantity=1,
            )
        ),
        "provider_cost_missing",
    )
