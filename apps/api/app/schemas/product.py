from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductRead(BaseModel):
    """Public response schema for catalog product records.

    The schema exposes the fields customers need to browse catalog products
    without exposing internal visibility state.
    """

    id: int
    name: str
    description: str | None
    category_id: int
    base_price: Decimal

    model_config = ConfigDict(from_attributes=True)
