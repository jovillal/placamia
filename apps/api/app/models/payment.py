from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from app.core.database import Base
from app.domain.payment_lifecycle import PaymentStatus
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.payment_provider_event import PaymentProviderEvent
    from app.models.payment_provider_transaction import PaymentProviderTransaction


PAYMENT_STATUS_VALUES = tuple(status.value for status in PaymentStatus)
"""Database-supported canonical payment status values."""


class Payment(Base):
    """Persisted payment attempt metadata for one backend-owned order.

    The model maps to the `payments` table and stores only payment-safe fields
    needed for status tracking and later trusted confirmation processing. It
    does not store card data, raw provider payloads, secrets, or provider
    handoff behavior.
    """

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            f"status IN {PAYMENT_STATUS_VALUES}",
            name="ck_payments_status_supported",
        ),
        CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name="ck_payments_currency_iso_uppercase",
        ),
        CheckConstraint(
            "amount >= 0",
            name="ck_payments_amount_nonnegative",
        ),
        UniqueConstraint(
            "order_id",
            "payment_provider_reference",
            name="uq_payments_order_provider_reference",
        ),
        UniqueConstraint(
            "provider_code",
            "merchant_reference",
            name="uq_payments_provider_merchant_reference",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"),
        nullable=False,
        index=True,
    )
    provider_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    merchant_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    provider_checkout_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PaymentStatus.INITIATED.value,
        server_default=PaymentStatus.INITIATED.value,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_provider_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    checkout_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="payments",
    )
    provider_transactions: Mapped[list["PaymentProviderTransaction"]] = relationship(
        "PaymentProviderTransaction",
        back_populates="payment",
    )
    provider_events: Mapped[list["PaymentProviderEvent"]] = relationship(
        "PaymentProviderEvent",
        back_populates="payment",
    )
