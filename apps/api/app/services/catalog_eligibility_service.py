from __future__ import annotations

from dataclasses import dataclass

from app.domain.provider_adapter import (
    AvailabilityState,
    CatalogItemType,
    EligibilityState,
    ProviderAdapter,
    ProviderItemRequest,
)
from app.models.kit import Kit
from app.models.product import Product

DEFAULT_PROVIDER_ID = "local-provider"


@dataclass(frozen=True)
class CatalogEligibility:
    """Backend-derived public eligibility signals for catalog responses."""

    availability_state: AvailabilityState
    direct_checkout_eligible: bool
    eligibility_reason: str | None
    production_lead_time_days: int | None
    dispatch_lead_time_days: int | None


class CatalogEligibilityService:
    """Derive catalog purchasability from backend state and provider adapter data."""

    def __init__(
        self,
        provider_adapter: ProviderAdapter,
        assigned_provider_id: str = DEFAULT_PROVIDER_ID,
    ) -> None:
        """Store the adapter and backend-selected provider identifier.

        Args:
            provider_adapter: Adapter boundary used for provider availability,
                eligibility, and lead-time signals.
            assigned_provider_id: Backend-selected provider identifier. The
                frontend must not supply or override this value.
        """
        self.provider_adapter = provider_adapter
        self.assigned_provider_id = assigned_provider_id

    def evaluate_product(
        self,
        product: Product,
        quantity: int = 1,
    ) -> CatalogEligibility:
        """Return adapter-backed direct-checkout eligibility for one Product.

        Args:
            product: Product model instance from backend persistence.
            quantity: Backend-owned quantity to evaluate through the provider
                adapter boundary.

        Returns:
            Public eligibility signals derived from backend state and provider
            adapter responses.
        """
        request = self._build_item_request(
            item_type=CatalogItemType.PRODUCT,
            item_id=product.id,
            quantity=quantity,
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
        reason = self._reason_for_product(
            product=product,
            direct_checkout_eligible=direct_checkout_eligible,
            provider_priceable=provider_priceable,
            adapter_reason=(
                adapter_eligibility.reason_code
                or pricing.reason_code
                or availability.reason_code
            ),
        )

        return CatalogEligibility(
            availability_state=availability.state,
            direct_checkout_eligible=direct_checkout_eligible,
            eligibility_reason=reason,
            production_lead_time_days=lead_time.production_days,
            dispatch_lead_time_days=lead_time.dispatch_days,
        )

    def evaluate_kit(self, kit: Kit) -> CatalogEligibility:
        """Return adapter-backed direct-checkout eligibility for one Kit.

        Args:
            kit: Kit model instance with KitItems and Products loaded.

        Returns:
            Public eligibility signals derived from required kit contents,
            backend priceability assumptions, and provider adapter responses.
        """
        request = self._build_item_request(
            item_type=CatalogItemType.KIT,
            item_id=kit.id,
            quantity=1,
        )
        availability = self.provider_adapter.check_availability(request)
        adapter_eligibility = self.provider_adapter.check_direct_checkout_eligibility(
            request
        )
        lead_time = self.provider_adapter.estimate_lead_time(request)

        content_reason = self._kit_content_reason(kit)
        direct_checkout_eligible = (
            kit.is_active
            and content_reason is None
            and adapter_eligibility.state is EligibilityState.ELIGIBLE
        )
        reason = None
        if not direct_checkout_eligible:
            reason = (
                content_reason
                or adapter_eligibility.reason_code
                or availability.reason_code
                or "not_eligible"
            )

        return CatalogEligibility(
            availability_state=availability.state,
            direct_checkout_eligible=direct_checkout_eligible,
            eligibility_reason=reason,
            production_lead_time_days=lead_time.production_days,
            dispatch_lead_time_days=lead_time.dispatch_days,
        )

    def _build_item_request(
        self,
        item_type: CatalogItemType,
        item_id: int,
        quantity: int,
    ) -> ProviderItemRequest:
        """Build a backend-owned provider adapter item request."""
        return ProviderItemRequest(
            item_type=item_type,
            item_id=item_id,
            quantity=quantity,
            assigned_provider_id=self.assigned_provider_id,
            options={},
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

    def _kit_content_reason(self, kit: Kit) -> str | None:
        """Return the first backend reason that makes kit contents ineligible."""
        if not kit.is_active:
            return "inactive"
        if not kit.kit_items:
            return "empty_kit"
        for item in kit.kit_items:
            if not item.product.is_active:
                return "inactive_kit_item"
            product_eligibility = self.evaluate_product(
                product=item.product,
                quantity=item.quantity,
            )
            if not product_eligibility.direct_checkout_eligible:
                return product_eligibility.eligibility_reason
        return None
