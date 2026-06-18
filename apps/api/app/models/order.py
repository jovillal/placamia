from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from app.core.database import Base
from app.domain.order_lifecycle import OrderStatus
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.order_item import OrderItem
    from app.models.payment import Payment
    from app.models.user import User


ORDER_STATUS_VALUES = tuple(status.value for status in OrderStatus)
"""Database-supported Path A order status values."""

CANCELLATION_REQUEST_SOURCE_VALUES = (
    OrderStatus.CONFIRMED.value,
    OrderStatus.ACCEPTED.value,
    OrderStatus.IN_PRODUCTION.value,
)
"""Statuses from which a paid customer cancellation request may originate."""


class Order(Base):
    """Customer order created from backend-validated checkout state.

    The model maps to the `orders` table and stores ownership, lifecycle state,
    backend-calculated totals, payment/provider references, cancellation
    provenance, terms acknowledgement, and timestamps. It does not accept or
    verify frontend ownership claims, calculate prices, create payments, or send
    provider handoffs.
    """

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            f"status IN {ORDER_STATUS_VALUES}",
            name="ck_orders_status_supported",
        ),
        CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name="ck_orders_currency_iso_uppercase",
        ),
        CheckConstraint(
            "subtotal_amount >= 0",
            name="ck_orders_subtotal_amount_nonnegative",
        ),
        CheckConstraint(
            "discount_amount >= 0",
            name="ck_orders_discount_amount_nonnegative",
        ),
        CheckConstraint(
            "tax_amount >= 0",
            name="ck_orders_tax_amount_nonnegative",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="ck_orders_total_amount_nonnegative",
        ),
        CheckConstraint(
            "("
            "status = 'cancellation_requested' "
            f"AND cancellation_requested_from IN {CANCELLATION_REQUEST_SOURCE_VALUES}"
            ") OR ("
            "status != 'cancellation_requested' "
            "AND cancellation_requested_from IS NULL"
            ")",
            name="ck_orders_cancellation_requested_from_matches_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=OrderStatus.DRAFT.value,
        server_default=OrderStatus.DRAFT.value,
        index=True,
    )
    cancellation_requested_from: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="COP",
        server_default="COP",
    )
    payment_provider_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    payment_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    assigned_provider_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_handoff_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    provider_handoff_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    terms_policy_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
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
    customer: Mapped["User"] = relationship(
        "User",
        back_populates="orders",
    )
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan",
    )
