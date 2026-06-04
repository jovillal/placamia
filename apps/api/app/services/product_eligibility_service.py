from __future__ import annotations

from dataclasses import dataclass

from app.domain.provider_adapter import (
    AvailabilityState,
    CatalogItemType,
    EligibilityState,
    ProviderAdapter,
    ProviderItemRequest,
)
from app.models.product import Product

DEFAULT_PROVIDER_ID = "local-provider"


@dataclass(frozen=True)
class ProductEligibility:
    """Backend-derived public direct-checkout signals for one Product."""

    availability_state: AvailabilityState
    direct_checkout_eligible: bool
    eligibility_reason: str | None
    production_lead_time_days: int | None
    dispatch_lead_time_days: int | None


class ProductEligibilityService:
    """Derive product purchasability from backend state and provider adapter data."""

    def __init__(
        self,
        provider_adapter: ProviderAdapter,
        assigned_provider_id: str = DEFAULT_PROVIDER_ID,
    ) -> None:
        """Store provider adapter dependencies for product eligibility checks.

        Args:
            provider_adapter: Backend-owned provider adapter boundary.
            assigned_provider_id: Backend-selected provider identifier. The
                frontend must not supply or override this value.
        """
        self.provider_adapter = provider_adapter
        self.assigned_provider_id = assigned_provider_id

    def evaluate_product(self, product: Product) -> ProductEligibility:
        """Return public eligibility fields for an active catalog Product.

        Args:
            product: Product model read from backend persistence.

        Returns:
            Backend-derived eligibility data for public product responses.

        Side effects:
            None.
        """
        request = ProviderItemRequest(
            item_type=CatalogItemType.PRODUCT,
            item_id=product.id,
            quantity=1,
            assigned_provider_id=self.assigned_provider_id,
            options={},
        )
        availability = self.provider_adapter.check_availability(request)
        pricing = self.provider_adapter.quote_pricing(request)
        adapter_eligibility = self.provider_adapter.check_direct_checkout_eligibility(
            request
        )
        lead_time = self.provider_adapter.estimate_lead_time(request)

        provider_priceable = (
            pricing.provider_cost is not None
            and pricing.supports_requested_configuration
        )
        direct_checkout_eligible = (
            product.is_active
            and product.base_price is not None
            and provider_priceable
            and adapter_eligibility.state is EligibilityState.ELIGIBLE
        )

        return ProductEligibility(
            availability_state=availability.state,
            direct_checkout_eligible=direct_checkout_eligible,
            eligibility_reason=self._reason_for_product(
                product=product,
                direct_checkout_eligible=direct_checkout_eligible,
                provider_priceable=provider_priceable,
                adapter_reason=(
                    adapter_eligibility.reason_code
                    or pricing.reason_code
                    or availability.reason_code
                ),
            ),
            production_lead_time_days=lead_time.production_days,
            dispatch_lead_time_days=lead_time.dispatch_days,
        )

    def _reason_for_product(
        self,
        product: Product,
        direct_checkout_eligible: bool,
        provider_priceable: bool,
        adapter_reason: str | None,
    ) -> str | None:
        """Return the public reason code for product ineligibility."""
        if direct_checkout_eligible:
            return None
        if not product.is_active:
            return "inactive"
        if product.base_price is None:
            return "not_priceable"
        if not provider_priceable:
            return adapter_reason or "provider_not_priceable"
        return adapter_reason or "not_eligible"
