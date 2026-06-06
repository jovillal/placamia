from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.domain.provider_adapter import (
    CatalogItemType,
    ProviderAdapter,
    ProviderItemRequest,
)
from app.models.kit import Kit
from app.models.product import Product
from app.services.kit_eligibility_service import KitEligibilityService
from app.services.product_eligibility_service import (
    DEFAULT_PROVIDER_ID,
    ProductEligibilityService,
)

MIN_PRICING_QUANTITY = 1
MAX_PRICING_QUANTITY = 100
SUPPORTED_PRICING_OPTIONS: frozenset[str] = frozenset()
FORBIDDEN_FRONTEND_PRICING_CLAIMS: frozenset[str] = frozenset(
    {
        "price",
        "base_price",
        "subtotal",
        "discount",
        "discounts",
        "tax",
        "taxes",
        "fee",
        "fees",
        "total",
        "final_amount",
        "checkout_total",
        "provider_cost",
        "provider_id",
        "provider_assignment",
        "assigned_provider_id",
        "user_id",
        "customer_id",
        "owner_id",
        "role",
        "is_admin",
        "availability_state",
        "direct_checkout_eligible",
        "lead_time",
        "production_lead_time_days",
        "dispatch_lead_time_days",
        "supports_requested_configuration",
    }
)


class PricingItemType(StrEnum):
    """Catalog item types accepted by the Path A pricing contract."""

    PRODUCT = "product"
    KIT = "kit"
    DESIGN = "design"


@dataclass(frozen=True)
class PricingRejected(ValueError):
    """Raised when an item or request cannot receive a Path A checkout price.

    Attributes:
        code: Stable rejection reason for services and tests.
        message: Human-readable explanation of the rejection.
    """

    code: str
    message: str

    def __str__(self) -> str:
        """Return the human-readable rejection message."""
        return self.message


@dataclass(frozen=True)
class PathAPricingRequest:
    """Backend-owned pricing request for a direct-checkout item.

    Attributes:
        item_type: Product, kit, or design pricing contract target.
        item: Backend-loaded model or validated design pricing payload.
        quantity: Backend-validated requested item quantity.
        options: Backend-validated material, size, finish, template, or design
            options. No product/kit options are supported yet.
        frontend_claims: Raw frontend price, provider, availability, discount,
            or total claims to reject before calculation.
    """

    item_type: PricingItemType
    item: Product | Kit | object
    quantity: int
    options: dict[str, Any] = field(default_factory=dict)
    frontend_claims: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PathAPricingValidation:
    """Validated Path A pricing contract inputs for one item.

    This result intentionally contains no customer-facing unit price, subtotal,
    total, margin, tax, fee, or discount calculation. It confirms only that the
    backend-loaded item passed rejection rules and that provider cost/capability
    input is available for a future pricing calculation slice.
    """

    item_type: PricingItemType
    item_id: int
    quantity: int
    currency: str
    provider_cost_input_available: bool
    provider_quote_reference: str | None


@dataclass(frozen=True)
class PathAPricingPreview:
    """Temporary MVP customer-facing pricing preview for one Path A item.

    Attributes:
        item_type: Catalog item type being previewed.
        item_id: Backend-loaded catalog item identifier.
        quantity: Backend-validated requested quantity.
        currency: Currency code used by the preview.
        customer_unit_price: Temporary customer unit price.
        customer_subtotal: Temporary subtotal before future tax, fee, discount,
            margin, or checkout finalization rules.
        customer_total: Temporary preview total. For #27 only, this equals the
            subtotal.
        pricing_rule: Stable name for the temporary rule used.
        provider_quote_reference: Provider adapter trace reference. This is not
            a customer-facing price or provider cost.
    """

    item_type: PricingItemType
    item_id: int
    quantity: int
    currency: str
    customer_unit_price: Decimal
    customer_subtotal: Decimal
    customer_total: Decimal
    pricing_rule: str
    provider_quote_reference: str | None


class PathAPricingService:
    """Validate Path A pricing contracts before calculation is implemented."""

    def __init__(
        self,
        provider_adapter: ProviderAdapter,
        currency: str = "COP",
        assigned_provider_id: str = DEFAULT_PROVIDER_ID,
    ) -> None:
        """Store pricing dependencies.

        Args:
            provider_adapter: Backend-owned provider adapter boundary used for
                availability, eligibility, and provider cost/capability input.
            currency: Currency code used in customer-facing pricing results.
            assigned_provider_id: Backend-selected provider identifier used for
                adapter pricing requests.
        """
        self.provider_adapter = provider_adapter
        self.currency = currency
        self.assigned_provider_id = assigned_provider_id

    def validate_pricing_request(
        self,
        request: PathAPricingRequest,
    ) -> PathAPricingValidation:
        """Validate a pricing request or raise a deterministic rejection.

        Args:
            request: Backend-owned pricing request.

        Returns:
            Validated pricing contract inputs for a later calculation step.

        Raises:
            PricingRejected: If request data is unsafe, unsupported, or not
                direct-checkout eligible.
        """
        self._reject_frontend_pricing_claims(request.frontend_claims)
        self._validate_quantity(request.quantity)
        self._validate_options(request.options)

        if request.item_type is PricingItemType.PRODUCT:
            return self._validate_product_pricing(request)
        if request.item_type is PricingItemType.KIT:
            return self._validate_kit_pricing(request)
        if request.item_type is PricingItemType.DESIGN:
            raise PricingRejected(
                code="design_pricing_contract_only",
                message=(
                    "Design pricing is part of the Path A contract, but full "
                    "implementation is deferred until design pricing rules are "
                    "defined."
                ),
            )

        raise PricingRejected(
            code="unsupported_item_type",
            message="Pricing item type is not supported.",
        )

    def preview_price(self, request: PathAPricingRequest) -> PathAPricingPreview:
        """Return a temporary MVP pricing preview for an eligible Product.

        Args:
            request: Backend-owned pricing request.

        Returns:
            Customer-facing product preview amounts calculated by the temporary
            #27 MVP rule.

        Raises:
            PricingRejected: If request data is unsafe, unsupported, not
                direct-checkout eligible, or not supported by #27.
        """
        self._reject_frontend_pricing_claims(request.frontend_claims)
        self._validate_quantity(request.quantity)
        self._validate_options(request.options)

        if request.item_type is PricingItemType.PRODUCT:
            validation = self._validate_product_pricing(request)
            product = self._require_product(request.item)
            unit_price = product.base_price
            subtotal = unit_price * request.quantity
            return PathAPricingPreview(
                item_type=PricingItemType.PRODUCT,
                item_id=product.id,
                quantity=request.quantity,
                currency=self.currency,
                customer_unit_price=unit_price,
                customer_subtotal=subtotal,
                customer_total=subtotal,
                pricing_rule="temporary_product_base_price_v1",
                provider_quote_reference=validation.provider_quote_reference,
            )

        if request.item_type is PricingItemType.KIT:
            raise PricingRejected(
                code="kit_pricing_deferred",
                message=(
                    "Kit pricing preview is deferred until a documented kit "
                    "pricing method exists."
                ),
            )

        if request.item_type is PricingItemType.DESIGN:
            raise PricingRejected(
                code="design_pricing_contract_only",
                message=(
                    "Design pricing is part of the Path A contract, but full "
                    "implementation is deferred until design pricing rules are "
                    "defined."
                ),
            )

        raise PricingRejected(
            code="unsupported_item_type",
            message="Pricing preview item type is not supported.",
        )

    def _validate_product_pricing(
        self,
        request: PathAPricingRequest,
    ) -> PathAPricingValidation:
        """Validate pricing contract inputs for one Product request."""
        product = self._require_product(request.item)
        eligibility_service = ProductEligibilityService(self.provider_adapter)
        eligibility = eligibility_service.evaluate_product(
            product=product,
            quantity=request.quantity,
        )
        if not eligibility.direct_checkout_eligible:
            raise PricingRejected(
                code=eligibility.eligibility_reason or "not_eligible",
                message="Product is not eligible for direct checkout pricing.",
            )

        quote_reference = self._provider_quote_reference_for_product(
            product.id,
            request.quantity,
        )
        return PathAPricingValidation(
            item_type=PricingItemType.PRODUCT,
            item_id=product.id,
            quantity=request.quantity,
            currency=self.currency,
            provider_cost_input_available=True,
            provider_quote_reference=quote_reference,
        )

    def _validate_kit_pricing(
        self,
        request: PathAPricingRequest,
    ) -> PathAPricingValidation:
        """Validate pricing contract inputs for one Kit request."""
        kit = self._require_kit(request.item)
        eligibility_service = KitEligibilityService(self.provider_adapter)
        eligibility = eligibility_service.evaluate_kit(kit)
        if not eligibility.direct_checkout_eligible:
            raise PricingRejected(
                code=eligibility.eligibility_reason or "not_eligible",
                message="Kit is not eligible for direct checkout pricing.",
            )

        quote_reference = self._provider_quote_reference_for_kit(
            kit.id,
            request.quantity,
        )
        return PathAPricingValidation(
            item_type=PricingItemType.KIT,
            item_id=kit.id,
            quantity=request.quantity,
            currency=self.currency,
            provider_cost_input_available=True,
            provider_quote_reference=quote_reference,
        )

    def _reject_frontend_pricing_claims(
        self,
        frontend_claims: dict[str, Any],
    ) -> None:
        """Reject frontend-provided pricing or provider truth claims."""
        if not frontend_claims:
            return

        forbidden_claims = set(frontend_claims) & FORBIDDEN_FRONTEND_PRICING_CLAIMS
        if forbidden_claims:
            raise PricingRejected(
                code="frontend_pricing_claim_not_allowed",
                message=(
                    "Frontend price, total, discount, provider, availability, "
                    "or eligibility claims are not accepted."
                ),
            )

    def _validate_quantity(self, quantity: int) -> None:
        """Reject non-integer or abusive pricing quantities."""
        if not isinstance(quantity, int) or isinstance(quantity, bool):
            raise PricingRejected(
                code="invalid_quantity",
                message="Quantity must be an integer.",
            )
        if quantity < MIN_PRICING_QUANTITY:
            raise PricingRejected(
                code="quantity_too_low",
                message="Quantity must be at least one.",
            )
        if quantity > MAX_PRICING_QUANTITY:
            raise PricingRejected(
                code="quantity_too_high",
                message="Quantity exceeds the Path A pricing limit.",
            )

    def _validate_options(self, options: dict[str, Any]) -> None:
        """Reject unsupported material, size, finish, or template options."""
        if not isinstance(options, dict):
            raise PricingRejected(
                code="invalid_configuration",
                message="Pricing options must be an object.",
            )
        if set(options) - SUPPORTED_PRICING_OPTIONS:
            raise PricingRejected(
                code="invalid_configuration",
                message="Submitted pricing options are not supported.",
            )

    def _provider_quote_reference_for_product(
        self,
        product_id: int,
        quantity: int,
    ) -> str | None:
        """Validate provider cost input and return trace reference for Product."""
        pricing = self.provider_adapter.quote_pricing(
            ProviderItemRequest(
                item_type=CatalogItemType.PRODUCT,
                item_id=product_id,
                quantity=quantity,
                assigned_provider_id=self.assigned_provider_id,
                options={},
            )
        )
        if pricing.provider_cost is None:
            raise PricingRejected(
                code=pricing.reason_code or "provider_cost_missing",
                message="Provider cost input is required for Path A pricing.",
            )
        return pricing.quote_reference

    def _provider_quote_reference_for_kit(
        self,
        kit_id: int,
        quantity: int,
    ) -> str | None:
        """Validate provider cost input and return trace reference for Kit."""
        pricing = self.provider_adapter.quote_pricing(
            ProviderItemRequest(
                item_type=CatalogItemType.KIT,
                item_id=kit_id,
                quantity=quantity,
                assigned_provider_id=self.assigned_provider_id,
                options={},
            )
        )
        if pricing.provider_cost is None:
            raise PricingRejected(
                code=pricing.reason_code or "provider_cost_missing",
                message="Provider cost input is required for Path A pricing.",
            )
        return pricing.quote_reference

    def _require_product(self, item: Product | Kit | object) -> Product:
        """Return item as Product or reject mismatched pricing input."""
        if not isinstance(item, Product):
            raise PricingRejected(
                code="invalid_pricing_item",
                message="Product pricing requires a Product model.",
            )
        return item

    def _require_kit(self, item: Product | Kit | object) -> Kit:
        """Return item as Kit or reject mismatched pricing input."""
        if not isinstance(item, Kit):
            raise PricingRejected(
                code="invalid_pricing_item",
                message="Kit pricing requires a Kit model.",
            )
        return item
