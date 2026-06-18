from app.models.payment import Payment
from sqlalchemy import select
from sqlalchemy.orm import Session


class PaymentRepository:
    """Data access layer for persisted backend-owned Payment records.

    The repository receives a SQLAlchemy session and persists only payment-safe
    model data. It does not verify payment-provider events, initialize
    payments, store raw provider payloads, or trigger provider handoff.
    """

    def __init__(self, db: Session) -> None:
        """Store the database session used by payment queries and writes.

        Args:
            db: SQLAlchemy session bound to the current request or test.
        """
        self.db = db

    def create_payment(self, payment: Payment) -> Payment:
        """Stage one Payment record inside the current transaction.

        Args:
            payment: Payment model populated from backend-owned payment-safe
                fields.

        Returns:
            The persisted Payment with database-generated identifiers populated.

        Side effects:
            Adds the payment row to the current database transaction, flushes
            it so generated identifiers are available, and refreshes the
            instance. The caller remains responsible for committing or rolling
            back.
        """
        self.db.add(payment)
        self.db.flush()
        self.db.refresh(payment)
        return payment

    def get_payment_by_id(self, payment_id: int) -> Payment | None:
        """Return one Payment by primary key.

        Args:
            payment_id: Payment identifier to look up.

        Returns:
            The matching Payment model instance, or None when no row exists.
        """
        return self.db.get(Payment, payment_id)

    def get_payments_for_order(self, order_id: int) -> list[Payment]:
        """Return Payment records for one Order sorted by newest first.

        Args:
            order_id: Backend Order identifier.

        Returns:
            Matching payments sorted by newest first.
        """
        result = self.db.execute(
            select(Payment)
            .where(Payment.order_id == order_id)
            .order_by(Payment.created_at.desc(), Payment.id.desc())
        )
        return list(result.scalars().all())

    def get_payment_by_provider_reference(
        self,
        provider_reference: str,
    ) -> Payment | None:
        """Return one Payment by payment-provider reference.

        Args:
            provider_reference: Payment-provider reference to look up.

        Returns:
            The matching Payment model instance, or None when no row exists.
        """
        result = self.db.execute(
            select(Payment).where(
                Payment.payment_provider_reference == provider_reference
            )
        )
        return result.scalar_one_or_none()
