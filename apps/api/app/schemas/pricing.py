from decimal import Decimal
from typing import Any

from app.services.pricing_service import PricingItemType
from pydantic import BaseModel, ConfigDict, Field


class PricingQuoteRequest(BaseModel):
    """Request schema for a Path A pricing preview.

    Known fields are validated explicitly. Extra frontend-supplied fields are
    preserved so pricing services can reject price, provider, availability,
    eligibility, ownership, or total claims instead of silently trusting them.
    """

    item_type: PricingItemType
    item_id: int = Field(gt=0)
    quantity: int
    options: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")

    def frontend_claims(self) -> dict[str, Any]:
        """Return extra request fields that must be rejected by pricing rules."""
        return dict(self.model_extra or {})


class PricingQuoteResponse(BaseModel):
    """Response schema for a temporary product pricing preview."""

    item_type: PricingItemType
    item_id: int
    quantity: int
    currency: str
    customer_unit_price: Decimal
    customer_subtotal: Decimal
    preview_total: Decimal
    pricing_rule: str
    provider_quote_reference: str | None
