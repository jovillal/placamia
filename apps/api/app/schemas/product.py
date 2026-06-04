from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductRead(BaseModel):
    """Public response schema for catalog product records.

    The schema exposes the fields customers need to browse catalog products
    with backend-derived direct-checkout signals. Availability and eligibility
    fields are output-only; frontend-provided values must not influence them.
    """

    id: int
    name: str
    description: str | None
    category_id: int
    base_price: Decimal
    availability_state: str
    direct_checkout_eligible: bool
    eligibility_reason: str | None
    production_lead_time_days: int | None
    dispatch_lead_time_days: int | None

    model_config = ConfigDict(from_attributes=True)
