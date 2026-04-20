from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CategoryRead(BaseModel):
    """Response schema for catalog category records.

    The schema is built from SQLAlchemy category objects and serialized by
    FastAPI for read endpoints.
    """

    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
