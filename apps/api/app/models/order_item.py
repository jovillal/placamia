from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.core.database import Base
from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.design import Design
    from app.models.kit import Kit
    from app.models.order import Order
    from app.models.product import Product
    from app.models.template import Template


class OrderItemType:
    """Supported immutable order item snapshot types."""

    PRODUCT = "product"
    KIT = "kit"
    DESIGN = "design"


ORDER_ITEM_TYPE_VALUES = (
    OrderItemType.PRODUCT,
    OrderItemType.KIT,
    OrderItemType.DESIGN,
)
"""Database-supported order item snapshot types."""


class OrderItem(Base):
    """Immutable purchased item snapshot inside a customer Order.

    The model maps to the `order_items` table and stores customer-safe display
    metadata, selected options, backend-calculated pricing, provider assignment
    data, and provider payload snapshot data captured at order time. It may
    reference catalog records for traceability, but tracking and handoff must
    use the snapshot fields instead of recomputing from mutable catalog data.
    """

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint(
            f"item_type IN {ORDER_ITEM_TYPE_VALUES}",
            name="ck_order_items_item_type_supported",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_order_items_quantity_positive",
        ),
        CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name="ck_order_items_currency_iso_uppercase",
        ),
        CheckConstraint(
            "unit_price_amount >= 0",
            name="ck_order_items_unit_price_amount_nonnegative",
        ),
        CheckConstraint(
            "line_subtotal_amount >= 0",
            name="ck_order_items_line_subtotal_amount_nonnegative",
        ),
        CheckConstraint(
            "line_discount_amount >= 0",
            name="ck_order_items_line_discount_amount_nonnegative",
        ),
        CheckConstraint(
            "line_tax_amount >= 0",
            name="ck_order_items_line_tax_amount_nonnegative",
        ),
        CheckConstraint(
            "line_total_amount >= 0",
            name="ck_order_items_line_total_amount_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"),
        nullable=False,
        index=True,
    )
    item_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"),
        nullable=True,
        index=True,
    )
    kit_id: Mapped[int | None] = mapped_column(
        ForeignKey("kits.id"),
        nullable=True,
        index=True,
    )
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("templates.id"),
        nullable=True,
        index=True,
    )
    design_id: Mapped[int | None] = mapped_column(
        ForeignKey("designs.id"),
        nullable=True,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_safe_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_options: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_subtotal_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    line_discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    line_tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    line_total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="COP",
        server_default="COP",
    )
    assigned_provider_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_pricing_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    provider_payload_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="items",
    )
    product: Mapped["Product | None"] = relationship("Product")
    kit: Mapped["Kit | None"] = relationship("Kit")
    template: Mapped["Template | None"] = relationship("Template")
    design: Mapped["Design | None"] = relationship("Design")
