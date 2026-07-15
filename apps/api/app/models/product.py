from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from app.core.database import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.kit_item import KitItem
    from app.models.template import Template


class Product(Base):
    """Sellable catalog item assigned to a category.

    The model maps to the `products` table and stores basic catalog metadata,
    base pricing, activation state, and database-managed timestamps.
    """

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"),
        nullable=False,
        index=True,
    )
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
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
    category: Mapped["Category"] = relationship(
        "Category",
        back_populates="products",
    )
    kit_items: Mapped[list[KitItem]] = relationship(
        "KitItem",
        back_populates="product",
    )
    templates: Mapped[list[Template]] = relationship(
        "Template",
        back_populates="product",
    )
