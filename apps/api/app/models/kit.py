from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.kit_item import KitItem


class Kit(Base):
    """Curated bundle of products shown in the customer catalog.

    The model maps to the `kits` table and stores read-only MVP catalog
    metadata for sellable product bundles. Pricing, discounts, and checkout
    behavior belong to later scopes.
    """

    __tablename__ = "kits"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    kit_items: Mapped[list[KitItem]] = relationship(
        "KitItem",
        back_populates="kit",
    )
