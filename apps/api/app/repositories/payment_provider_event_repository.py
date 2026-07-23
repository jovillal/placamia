from datetime import datetime

from app.models.payment import Payment
from app.models.payment_provider_event import PaymentProviderEvent
from app.models.payment_provider_transaction import PaymentProviderTransaction
from sqlalchemy import select
from sqlalchemy.orm import Session


class PaymentProviderEventRepository:
    """Persist and read safe provider event identity and integrity metadata."""

    def __init__(self, db: Session) -> None:
        """Store the caller-owned database session."""
        self.db = db

    def create_event(
        self,
        *,
        payment: Payment,
        payment_provider_transaction: PaymentProviderTransaction | None,
        provider_event_reference: str,
        payload_hash: str,
        provider_occurred_at: datetime | None,
    ) -> PaymentProviderEvent:
        """Stage safe metadata for one authenticated provider event.

        Args:
            payment: Persisted owning Payment whose provider code is canonical.
            payment_provider_transaction: Optional linked transaction belonging
                to the same Payment and provider.
            provider_event_reference: Independently derived replay identity.
            payload_hash: Digest of the authenticated provider representation.
            provider_occurred_at: Provider event occurrence time when known.

        Returns:
            The staged safe provider event metadata.

        Side effects:
            Validates optional linkage and flushes one event row without commit.

        Raises:
            ValueError: If the linked transaction does not belong to Payment.
        """
        if payment_provider_transaction is not None and (
            payment_provider_transaction.payment_id != payment.id
            or payment_provider_transaction.provider_code != payment.provider_code
        ):
            raise ValueError(
                "Provider event transaction must belong to the same Payment."
            )

        event = PaymentProviderEvent(
            payment_id=payment.id,
            payment_provider_transaction_id=(
                payment_provider_transaction.id
                if payment_provider_transaction is not None
                else None
            ),
            provider_code=payment.provider_code,
            provider_event_reference=provider_event_reference,
            payload_hash=payload_hash,
            provider_occurred_at=provider_occurred_at,
        )
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event

    def get_event_by_provider_identity(
        self,
        provider_code: str,
        provider_event_reference: str,
    ) -> PaymentProviderEvent | None:
        """Return one event by provider-scoped replay identity."""
        return self.db.scalar(
            select(PaymentProviderEvent).where(
                PaymentProviderEvent.provider_code == provider_code,
                PaymentProviderEvent.provider_event_reference
                == provider_event_reference,
            )
        )

    def list_events_for_payment(self, payment_id: int) -> list[PaymentProviderEvent]:
        """Return all safe event records for one Payment in id order."""
        result = self.db.execute(
            select(PaymentProviderEvent)
            .where(PaymentProviderEvent.payment_id == payment_id)
            .order_by(PaymentProviderEvent.id.asc())
        )
        return list(result.scalars().all())
