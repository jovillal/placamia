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
from app.models.kit_item import KitItem
from app.services.product_eligibility_service import (
    DEFAULT_PROVIDER_ID,
    ProductEligibilityService,
)

KIT_CONTENTS_UNAVAILABLE_REASON = "kit_contents_unavailable"


@dataclass(frozen=True)
class KitEligibility:
    """Backend-derived public direct-checkout signals for one Kit."""

    availability_state: AvailabilityState
    direct_checkout_eligible: bool
    eligibility_reason: str | None
    production_lead_time_days: int | None
    dispatch_lead_time_days: int | None


class KitEligibilityService:
    """Derive kit purchasability from required contents and adapter responses."""

    def __init__(
        self,
        provider_adapter: ProviderAdapter,
        assigned_provider_id: str = DEFAULT_PROVIDER_ID,
    ) -> None:
        """Store provider adapter dependencies for kit eligibility checks.

        Args:
            provider_adapter: Backend-owned provider adapter boundary.
            assigned_provider_id: Backend-selected provider identifier. The
                frontend must not supply or override this value.
        """
        self.provider_adapter = provider_adapter
        self.assigned_provider_id = assigned_provider_id
        self.product_eligibility_service = ProductEligibilityService(
            provider_adapter=provider_adapter,
            assigned_provider_id=assigned_provider_id,
        )

    def evaluate_kit(self, kit: Kit, quantity: int = 1) -> KitEligibility:
        """Return public eligibility fields for an active catalog Kit.

        Args:
            kit: Kit model read from backend persistence with KitItems loaded.
            quantity: Requested Kit quantity used for Kit provider checks and
                effective required-content quantities.

        Returns:
            Backend-derived eligibility data for public kit responses.

        Side effects:
            None.
        """
        request = ProviderItemRequest(
            item_type=CatalogItemType.KIT,
            item_id=kit.id,
            quantity=quantity,
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
        content_reason = self._required_content_reason(kit.kit_items, quantity)
        direct_checkout_eligible = (
            kit.is_active
            and content_reason is None
            and provider_priceable
            and adapter_eligibility.state is EligibilityState.ELIGIBLE
        )

        return KitEligibility(
            availability_state=availability.state,
            direct_checkout_eligible=direct_checkout_eligible,
            eligibility_reason=self._reason_for_kit(
                kit=kit,
                content_reason=content_reason,
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

    def _required_content_reason(
        self,
        kit_items: list[KitItem],
        kit_quantity: int = 1,
    ) -> str | None:
        """Return the customer-safe reason required contents block checkout.

        Args:
            kit_items: Required KitItems loaded from backend persistence.
            kit_quantity: Requested number of Kits used to derive each
                required Product's effective quantity.

        Returns:
            The first visible active-content reason, an aggregate unavailable
            reason for omitted inactive contents, or None when all contents are
            eligible. The hidden all-inactive path retains its internal reason.

        Side effects:
            Calls the provider adapter through ProductEligibilityService for
            each active required content item until a blocker is found.
        """
        if not kit_items:
            return "empty_kit"

        ordered_items = sorted(
            kit_items,
            key=lambda item: item.id if item.id is not None else 0,
        )
        active_items = [item for item in ordered_items if item.product.is_active]
        if not active_items:
            return "inactive_kit_item"

        for item in active_items:
            product_eligibility = self.product_eligibility_service.evaluate_product(
                product=item.product,
                quantity=item.quantity * kit_quantity,
            )
            if not product_eligibility.direct_checkout_eligible:
                return product_eligibility.eligibility_reason or "kit_item_not_eligible"

        if len(active_items) < len(kit_items):
            return KIT_CONTENTS_UNAVAILABLE_REASON

        return None

    def _reason_for_kit(
        self,
        kit: Kit,
        content_reason: str | None,
        direct_checkout_eligible: bool,
        provider_priceable: bool,
        adapter_reason: str | None,
    ) -> str | None:
        """Return the public reason code for kit ineligibility."""
        if direct_checkout_eligible:
            return None
        if not kit.is_active:
            return "inactive"
        if content_reason is not None:
            return content_reason
        if not provider_priceable:
            return adapter_reason or "provider_not_priceable"
        return adapter_reason or "not_eligible"
