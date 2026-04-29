from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    """Response schema for authenticated user records.

    The schema exposes only the user fields that are safe for the current user
    to receive from protected endpoints.
    """

    id: int
    email: str
    full_name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
