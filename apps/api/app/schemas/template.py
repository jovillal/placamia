from typing import Literal

from pydantic import BaseModel, ConfigDict


class TemplateSummaryRead(BaseModel):
    """Customer-safe public summary for one active Template."""

    id: int
    name: str
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class TemplateFieldRead(BaseModel):
    """Customer-facing customization definition for an active TemplateField."""

    field_name: str
    field_type: Literal["text", "select", "number", "boolean"]
    is_required: bool
    allowed_values: list[str] | None
    display_order: int

    model_config = ConfigDict(from_attributes=True)


class TemplateDetailRead(TemplateSummaryRead):
    """Public Template detail with active customization fields."""

    fields: list[TemplateFieldRead]


class TemplateListResponse(BaseModel):
    """Response wrapper for the public Template collection endpoint."""

    data: list[TemplateSummaryRead]
