from datetime import datetime
from decimal import Decimal
from typing import Any

from app.schemas.checkout import CheckoutEligibilityRequest
from pydantic import BaseModel, ConfigDict


class OrderCreateRequest(CheckoutEligibilityRequest):
    """Request schema for creating a draft order from checkout input.

    The endpoint accepts the same known checkout fields as the #101 checkout
    eligibility gate. Extra frontend-supplied ownership, status, payment,
    provider handoff, pricing, or snapshot claims are preserved so the order
    creation service can reject them before any database mutation.
    """


class OrderItemRead(BaseModel):
    """Response schema for immutable order item snapshot rows."""

    id: int
    item_type: str
    product_id: int | None
    kit_id: int | None
    template_id: int | None
    design_id: int | None
    display_name: str
    customer_safe_description: str | None
    selected_options: dict[str, Any]
    quantity: int
    unit_price_amount: Decimal
    line_subtotal_amount: Decimal
    line_discount_amount: Decimal
    line_tax_amount: Decimal
    line_total_amount: Decimal
    currency: str
    assigned_provider_id: str
    provider_pricing_reference: str | None
    provider_payload_snapshot: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderRead(BaseModel):
    """Response schema for customer-owned draft order creation."""

    id: int
    customer_id: int
    status: str
    cancellation_requested_from: str | None
    subtotal_amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency: str
    payment_provider_reference: str | None
    payment_verified_at: datetime | None
    assigned_provider_id: str | None
    provider_handoff_reference: str | None
    provider_handoff_sent_at: datetime | None
    terms_policy_version: str | None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]

    model_config = ConfigDict(from_attributes=True)


class OrderStatusItemRead(BaseModel):
    """Customer-safe item snapshot shown in order tracking responses."""

    id: int
    item_type: str
    product_id: int | None
    kit_id: int | None
    template_id: int | None
    design_id: int | None
    display_name: str
    customer_safe_description: str | None
    selected_options: dict[str, Any]
    quantity: int
    line_total_amount: Decimal
    currency: str

    model_config = ConfigDict(from_attributes=True)


class OrderStatusRead(BaseModel):
    """Customer-safe order tracking response for the owning user."""

    id: int
    status: str
    cancellation_requested_from: str | None
    total_amount: Decimal
    currency: str
    created_at: datetime
    updated_at: datetime
    items: list[OrderStatusItemRead]

    model_config = ConfigDict(from_attributes=True)
