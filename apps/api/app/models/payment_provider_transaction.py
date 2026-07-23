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
    from app.models.payment import Payment
    from app.models.payment_provider_event import PaymentProviderEvent


NORMALIZED_PAYMENT_STATUS_VALUES = tuple(status.value for status in PaymentStatus)
"""Database-supported normalized provider transaction status values."""


class PaymentProviderTransaction(Base):
    """Safe persisted observation of one external payment transaction.

    Multiple transaction rows may belong to one Payment aggregate. The model
    stores identifiers, normalized financial values, statuses, and timestamps
    only; it never stores raw provider payloads or payment instrument data.
    """

    __tablename__ = "payment_provider_transactions"
    __table_args__ = (
        CheckConstraint(
            f"normalized_status IN {NORMALIZED_PAYMENT_STATUS_VALUES}",
            name="ck_payment_provider_transactions_status_supported",
        ),
        CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name="ck_payment_provider_transactions_currency_iso_uppercase",
        ),
        CheckConstraint(
            "amount >= 0",
            name="ck_payment_provider_transactions_amount_nonnegative",
        ),
        UniqueConstraint(
            "provider_code",
            "provider_transaction_reference",
            name="uq_payment_provider_transactions_provider_reference",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"),
        nullable=False,
        index=True,
    )
    provider_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    provider_transaction_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    provider_status: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_status: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    provider_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="provider_transactions",
    )
    provider_events: Mapped[list["PaymentProviderEvent"]] = relationship(
        "PaymentProviderEvent",
        back_populates="payment_provider_transaction",
    )
