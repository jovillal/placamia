from decimal import Decimal
from typing import Any

from app.services.pricing_service import PricingItemType
from pydantic import BaseModel, ConfigDict, Field


class CheckoutTermsAcknowledgement(BaseModel):
    """Frontend acknowledgement of the backend-selected checkout terms policy."""

    accepted: bool
    policy_version: str = Field(min_length=1)


class CheckoutEligibilityRequest(BaseModel):
    """Request schema for service-level checkout eligibility validation.

    Known fields identify the backend-loaded catalog item and terms
    acknowledgement. Extra frontend-supplied fields are preserved so checkout
    and pricing services can reject price, provider, availability, eligibility,
    ownership, lead-time, or total claims instead of trusting them.
    """

    item_type: PricingItemType
    item_id: int = Field(gt=0)
    quantity: int
    options: dict[str, Any] = Field(default_factory=dict)
    terms_acknowledgement: CheckoutTermsAcknowledgement | None = None

    model_config = ConfigDict(extra="allow")

    def frontend_claims(self) -> dict[str, Any]:
        """Return extra request fields that must be rejected by checkout rules."""
        return dict(self.model_extra or {})


class ValidatedCheckoutState(BaseModel):
    """Backend-owned checkout state suitable for later order/payment creation."""

    item_type: PricingItemType
    item_id: int
    quantity: int
    selected_options: dict[str, Any]
    currency: str
    customer_unit_price: Decimal
    customer_subtotal: Decimal
    preview_total: Decimal
    pricing_rule: str
    provider_quote_reference: str | None
    assigned_provider_id: str
    terms_policy_version: str
