from pydantic import BaseModel, ConfigDict


class KitItemRead(BaseModel):
    """Public response schema for one product reference inside a Kit."""

    product_id: int
    quantity: int

    model_config = ConfigDict(from_attributes=True)


class KitRead(BaseModel):
    """Public response schema for catalog Kit records.

    The schema exposes customer-facing bundle metadata and active product
    references with backend-derived direct-checkout signals. Eligibility fields
    are output-only; frontend-provided values must not influence them.
    """

    id: int
    name: str
    description: str | None
    items: list[KitItemRead]
    availability_state: str
    direct_checkout_eligible: bool
    eligibility_reason: str | None
    production_lead_time_days: int | None
    dispatch_lead_time_days: int | None
