from __future__ import annotations

from dataclasses import dataclass

from app.models.kit import Kit
from app.models.product import Product
from app.repositories.kit_repository import KitRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.checkout import CheckoutEligibilityRequest, ValidatedCheckoutState
from app.services.pricing_service import (
    PathAPricingRequest,
    PathAPricingService,
    PricingItemType,
    PricingRejected,
)
from app.services.product_eligibility_service import DEFAULT_PROVIDER_ID

DEFAULT_TERMS_POLICY_VERSION = "local-placeholder-cancellation-refund-v1"
"""Backend-owned placeholder terms policy version for local MVP checkout."""


@dataclass(frozen=True)
class CheckoutRejected(ValueError):
    """Raised when checkout eligibility validation rejects a request.

    Attributes:
        code: Stable rejection reason for routes, services, and tests.
        message: Human-readable explanation of the rejection.
    """

    code: str
    message: str

    def __str__(self) -> str:
        """Return the human-readable rejection message."""
        return self.message


class CheckoutEligibilityService:
    """Validate Path A checkout eligibility before order/payment initialization.

    The service loads catalog data from backend repositories, validates terms
    acknowledgement against the backend-selected policy version, recalculates
    pricing through the backend pricing service, and returns a persisted-order
    input snapshot for a later checkout slice. It does not create orders,
    initialize payments, or send provider handoffs.
    """

    def __init__(
        self,
        product_repository: ProductRepository,
        kit_repository: KitRepository,
        pricing_service: PathAPricingService,
        *,
        assigned_provider_id: str = DEFAULT_PROVIDER_ID,
        terms_policy_version: str = DEFAULT_TERMS_POLICY_VERSION,
    ) -> None:
        """Store checkout eligibility dependencies.

        Args:
            product_repository: Repository used to load backend-owned products.
            kit_repository: Repository used to load backend-owned kits.
            pricing_service: Service used to recalculate backend pricing and
                provider eligibility.
            assigned_provider_id: Backend-selected provider identifier to
                preserve in validated checkout state.
            terms_policy_version: Backend-selected cancellation/refund terms
                policy version that must be acknowledged before checkout.
        """
        self.product_repository = product_repository
        self.kit_repository = kit_repository
        self.pricing_service = pricing_service
        self.assigned_provider_id = assigned_provider_id
        self.terms_policy_version = terms_policy_version

    def validate_checkout(
        self,
        request: CheckoutEligibilityRequest,
    ) -> ValidatedCheckoutState:
        """Validate checkout eligibility and return backend-owned checkout state.

        Args:
            request: Checkout validation request built from frontend input.

        Returns:
            A validated checkout state containing item identity, quantity,
            customer-safe snapshot metadata, backend-calculated preview
            amounts, pricing rule, provider quote reference, backend provider
            assignment, selected options, and the acknowledged terms policy
            version.

        Raises:
            CheckoutRejected: If terms acknowledgement is missing/forged, the
                item is stale or unsupported, or pricing/provider eligibility
                rejects the request.

        Side effects:
            None. The service only reads catalog/provider/pricing inputs and
            must not create order, payment, or provider handoff records.
        """
        self._validate_terms_acknowledgement(request)
        item = self._load_catalog_item(request.item_type, request.item_id)

        try:
            preview = self.pricing_service.preview_price(
                PathAPricingRequest(
                    item_type=request.item_type,
                    item=item,
                    quantity=request.quantity,
                    options=request.options,
                    frontend_claims=request.frontend_claims(),
                )
            )
        except PricingRejected as exc:
            raise CheckoutRejected(code=exc.code, message=exc.message) from exc

        return ValidatedCheckoutState(
            item_type=preview.item_type,
            item_id=preview.item_id,
            product_id=item.id if isinstance(item, Product) else None,
            kit_id=item.id if isinstance(item, Kit) else None,
            template_id=None,
            design_id=None,
            display_name=self._snapshot_display_name(item),
            customer_safe_description=self._snapshot_description(item),
            quantity=preview.quantity,
            selected_options=request.options,
            currency=preview.currency,
            customer_unit_price=preview.customer_unit_price,
            customer_subtotal=preview.customer_subtotal,
            preview_total=preview.customer_total,
            pricing_rule=preview.pricing_rule,
            provider_quote_reference=preview.provider_quote_reference,
            assigned_provider_id=self.assigned_provider_id,
            terms_policy_version=self.terms_policy_version,
        )

    def _validate_terms_acknowledgement(
        self,
        request: CheckoutEligibilityRequest,
    ) -> None:
        """Reject missing, declined, or stale terms acknowledgement."""
        acknowledgement = request.terms_acknowledgement
        if acknowledgement is None or not acknowledgement.accepted:
            raise CheckoutRejected(
                code="terms_acknowledgement_required",
                message="Checkout requires accepted cancellation/refund terms.",
            )

        if acknowledgement.policy_version != self.terms_policy_version:
            raise CheckoutRejected(
                code="terms_policy_version_mismatch",
                message="Acknowledged terms policy version is not current.",
            )

    def _load_catalog_item(
        self,
        item_type: PricingItemType,
        item_id: int,
    ) -> Product | Kit | object:
        """Load the backend-owned catalog item used for pricing validation."""
        if item_type is PricingItemType.PRODUCT:
            product = self.product_repository.get_product_by_id(item_id)
            if product is None:
                raise CheckoutRejected(
                    code="catalog_item_not_found",
                    message="Requested product is no longer available.",
                )
            return product

        if item_type is PricingItemType.KIT:
            kit = self.kit_repository.get_kit_by_id(item_id)
            if kit is None:
                raise CheckoutRejected(
                    code="catalog_item_not_found",
                    message="Requested kit is no longer available.",
                )
            return kit

        if item_type is PricingItemType.DESIGN:
            return object()

        raise CheckoutRejected(
            code="unsupported_item_type",
            message="Checkout item type is not supported.",
        )

    def _snapshot_display_name(self, item: Product | Kit | object) -> str:
        """Return the customer-safe display name captured during validation."""
        if isinstance(item, Product | Kit):
            return item.name

        return "Custom design"

    def _snapshot_description(self, item: Product | Kit | object) -> str | None:
        """Return the customer-safe description captured during validation."""
        if isinstance(item, Product | Kit):
            return item.description

        return None
