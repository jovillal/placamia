from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.core.database import Base
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.payment import Payment


class PaymentWebhookEvent(Base):
    """Durable replay key for one trusted payment-provider webhook event.

    The model maps to the `payment_webhook_events` table and stores only the
    safe identifiers needed to prevent event replay. It does not store raw
    webhook payloads, signatures, secrets, card data, or full payment details.
    """

    __tablename__ = "payment_webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="payment_provider_webhook",
        server_default="payment_provider_webhook",
        index=True,
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id"),
        nullable=True,
        index=True,
    )
    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("payments.id"),
        nullable=True,
        index=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    order: Mapped["Order | None"] = relationship("Order")
    payment: Mapped["Payment | None"] = relationship("Payment")
