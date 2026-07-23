from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.core.database import Base
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.payment import Payment
    from app.models.payment_provider_transaction import PaymentProviderTransaction


class PaymentProviderEvent(Base):
    """Safe persisted metadata for one authenticated provider event.

    The provider event reference is stored independently from the payload hash
    so later webhook processing can distinguish matching delivery retries from
    conflicting content. Raw payloads and signatures are never stored.
    """

    __tablename__ = "payment_provider_events"
    __table_args__ = (
        UniqueConstraint(
            "provider_code",
            "provider_event_reference",
            name="uq_payment_provider_events_provider_reference",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"),
        nullable=False,
        index=True,
    )
    payment_provider_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_provider_transactions.id"),
        nullable=True,
        index=True,
    )
    provider_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    provider_event_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="provider_events",
    )
    payment_provider_transaction: Mapped["PaymentProviderTransaction | None"] = (
        relationship(
            "PaymentProviderTransaction",
            back_populates="provider_events",
        )
    )
