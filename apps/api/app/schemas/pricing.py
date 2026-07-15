from decimal import Decimal
from typing import Annotated, Any, Literal

from app.services.pricing_service import PricingItemType
from pydantic import BaseModel, ConfigDict, Field


class BasePricingQuoteRequest(BaseModel):
    """Shared request fields for one Path A pricing preview.

    Known fields are validated explicitly. Extra frontend-supplied fields are
    preserved so pricing services can reject price, provider, availability,
    eligibility, ownership, or total claims instead of silently trusting them.
    """

    item_id: int = Field(gt=0)

    model_config = ConfigDict(extra="allow")

    def frontend_claims(self) -> dict[str, Any]:
        """Return extra request fields that must be rejected by pricing rules."""
        return dict(self.model_extra or {})


class ProductPricingQuoteRequest(BasePricingQuoteRequest):
    """Existing Product pricing request contract."""

    item_type: Literal[PricingItemType.PRODUCT]
    quantity: int
    options: dict[str, Any] = Field(default_factory=dict)


class KitPricingQuoteRequest(BasePricingQuoteRequest):
    """Strict Kit request whose business values are validated by pricing rules."""

    item_type: Literal[PricingItemType.KIT]
    quantity: Any
    options: Any = Field(default_factory=dict)


class DesignPricingQuoteRequest(BasePricingQuoteRequest):
    """Strict authenticated persisted Design pricing request."""

    item_type: Literal[PricingItemType.DESIGN]
    quantity: Any

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"additionalProperties": False},
    )


PricingQuoteRequest = Annotated[
    ProductPricingQuoteRequest | KitPricingQuoteRequest | DesignPricingQuoteRequest,
    Field(discriminator="item_type"),
]
"""Discriminated Product, Kit, or Design pricing quote request."""


class ProductPricingQuoteResponse(BaseModel):
    """Response schema for a temporary product pricing preview."""

    item_type: Literal[PricingItemType.PRODUCT]
    item_id: int
    quantity: int
    currency: str
    customer_unit_price: Decimal
    customer_subtotal: Decimal
    preview_total: Decimal
    pricing_rule: str
    provider_quote_reference: str | None


class KitPricingLineResponse(BaseModel):
    """Customer-safe calculated pricing for one fixed Kit content line."""

    product_id: int
    product_name: str
    quantity_per_kit: int
    total_quantity: int
    customer_unit_price: Decimal
    customer_subtotal: Decimal


class KitPricingQuoteResponse(BaseModel):
    """Response schema for a temporary fixed-content Kit pricing preview."""

    item_type: Literal[PricingItemType.KIT]
    item_id: int
    quantity: int
    currency: str
    customer_unit_price: Decimal
    customer_subtotal: Decimal
    preview_total: Decimal
    pricing_rule: str
    provider_quote_reference: str | None
    lines: list[KitPricingLineResponse]


class DesignPricingQuoteResponse(BaseModel):
    """Response schema for a persisted customer-owned Design preview."""

    item_type: Literal[PricingItemType.DESIGN]
    item_id: int
    quantity: int
    currency: str
    customer_unit_price: Decimal
    customer_subtotal: Decimal
    preview_total: Decimal
    pricing_rule: str
    provider_quote_reference: str | None


PricingQuoteResponse = Annotated[
    ProductPricingQuoteResponse | KitPricingQuoteResponse | DesignPricingQuoteResponse,
    Field(discriminator="item_type"),
]
"""Discriminated Product, Kit, or Design pricing quote response."""
