from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.core.database import Base
from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.kit import Kit
    from app.models.product import Product


class KitItem(Base):
    """Quantity-bearing product entry inside a curated Kit.

    The model maps to the `kit_items` table and links one Kit to one existing
    Product. It stores bundle composition only and does not duplicate product
    metadata, prices, discounts, or checkout behavior.
    """

    __tablename__ = "kit_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    kit_id: Mapped[int] = mapped_column(
        ForeignKey("kits.id"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
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
    kit: Mapped["Kit"] = relationship(
        "Kit",
        back_populates="kit_items",
    )
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="kit_items",
    )
