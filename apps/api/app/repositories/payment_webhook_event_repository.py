from app.models.payment_webhook_event import PaymentWebhookEvent
from sqlalchemy.orm import Session


class PaymentWebhookEventRepository:
    """Data access layer for durable payment webhook replay keys.

    The repository receives a SQLAlchemy session and persists only minimal,
    payment-safe event identifiers. It does not verify signatures, parse raw
    provider payloads, confirm Orders, or trigger provider handoff.
    """

    def __init__(self, db: Session) -> None:
        """Store the database session used by webhook event queries and writes.

        Args:
            db: SQLAlchemy session bound to the current request or test.
        """
        self.db = db

    def create_event(
        self,
        *,
        event_id: str,
        source: str,
        order_id: int | None,
        payment_id: int | None = None,
    ) -> PaymentWebhookEvent:
        """Stage one replay event record inside the current transaction.

        Args:
            event_id: Provider-neutral webhook event identifier.
            source: Trusted webhook source label.
            order_id: Backend Order identifier when known.
            payment_id: Backend Payment identifier when known.

        Returns:
            The staged PaymentWebhookEvent with generated identifiers populated.

        Side effects:
            Adds the event row to the current transaction and flushes it so
            uniqueness conflicts surface before Payment, Order, or provider
            handoff mutation. The caller remains responsible for committing or
            rolling back.
        """
        event = PaymentWebhookEvent(
            event_id=event_id,
            source=source,
            order_id=order_id,
            payment_id=payment_id,
        )
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event

    def update_event(self, event: PaymentWebhookEvent) -> PaymentWebhookEvent:
        """Stage updates to one replay event inside the current transaction.

        Args:
            event: Existing PaymentWebhookEvent with safe linkage fields
                already updated.

        Returns:
            The refreshed event after pending changes are flushed.

        Side effects:
            Flushes event changes to the current transaction. The caller
            remains responsible for committing or rolling back.
        """
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event

    def get_event_by_event_id(self, event_id: str) -> PaymentWebhookEvent | None:
        """Return one replay event by provider-neutral event id.

        Args:
            event_id: Provider-neutral webhook event identifier.

        Returns:
            The matching replay event, or None when no row exists.
        """
        return (
            self.db.query(PaymentWebhookEvent)
            .filter(PaymentWebhookEvent.event_id == event_id)
            .one_or_none()
        )
