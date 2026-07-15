from typing import Any

from pydantic import BaseModel, ConfigDict


class DesignCreateRequest(BaseModel):
    """Strict input for one authenticated Design creation request."""

    template_id: int
    customization_values: dict[str, Any]

    model_config = ConfigDict(extra="forbid")


class DesignRead(BaseModel):
    """Customer-safe representation of one owned immutable Design."""

    id: int
    template_id: int
    customization_values: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
