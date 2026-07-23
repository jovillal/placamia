from app.models.payment import Payment
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session


LEGACY_GENERIC_PROVIDER_CODE = "legacy_generic"
LEGACY_PAYMENT_REFERENCE_PREFIX = "legacy-payment"


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

    def create_legacy_payment(self, payment: Payment) -> Payment:
        """Stage one transitional provider-neutral Payment with final identity.

        Args:
            payment: New Payment populated from backend-owned Order or trusted
                generic webhook state, without provider aggregate identity.

        Returns:
            The staged Payment with `legacy_generic` provider code and a final
            merchant reference derived from its allocated Payment id.

        Side effects:
            Allocates the Payment id, inserts one row with its final identity,
            and flushes it in the caller-owned transaction. No provisional
            merchant reference is written and no commit is performed.
        """
        payment.id = self._allocate_payment_id()
        payment.provider_code = LEGACY_GENERIC_PROVIDER_CODE
        payment.merchant_reference = f"{LEGACY_PAYMENT_REFERENCE_PREFIX}-{payment.id}"
        self.db.add(payment)
        self.db.flush()
        self.db.refresh(payment)
        return payment

    def _allocate_payment_id(self) -> int:
        """Allocate the next Payment id without inserting provisional data.

        Returns:
            The next database-owned integer Payment identifier.

        Side effects:
            Advances the PostgreSQL Payment sequence. SQLite test databases
            read the next available row id inside their isolated transaction.

        Raises:
            RuntimeError: If the configured database dialect is unsupported or
                PostgreSQL cannot resolve its Payment id sequence.
        """
        dialect_name = self.db.get_bind().dialect.name
        if dialect_name == "postgresql":
            payment_id = self.db.scalar(
                text("SELECT nextval(pg_get_serial_sequence('payments', 'id'))")
            )
        elif dialect_name == "sqlite":
            payment_id = self.db.scalar(
                select(func.coalesce(func.max(Payment.id), 0) + 1)
            )
        else:
            raise RuntimeError(
                f"Unsupported Payment id allocation dialect: {dialect_name}."
            )

        if payment_id is None:
            raise RuntimeError("Payment id sequence could not be resolved.")
        return int(payment_id)

    def update_payment(self, payment: Payment) -> Payment:
        """Stage updates to one Payment inside the current transaction.

        Args:
            payment: Existing Payment model with backend-validated field
                changes already applied.

        Returns:
            The refreshed Payment after pending changes are flushed.

        Side effects:
            Flushes payment changes to the current database transaction and
            refreshes the instance. The caller remains responsible for
            committing or rolling back.
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

    def get_payment_by_provider_identity(
        self,
        provider_code: str,
        merchant_reference: str,
    ) -> Payment | None:
        """Return one Payment by its provider-scoped merchant identity.

        Args:
            provider_code: Stable persisted payment-provider identifier.
            merchant_reference: Backend-owned merchant checkout reference.

        Returns:
            The matching Payment, or None when the identity is unknown.
        """
        return self.db.scalar(
            select(Payment).where(
                Payment.provider_code == provider_code,
                Payment.merchant_reference == merchant_reference,
            )
        )

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

    def get_payments_by_provider_reference(
        self,
        provider_reference: str,
    ) -> list[Payment]:
        """Return Payment records matching one payment-provider reference.

        Args:
            provider_reference: Payment-provider reference to look up.

        Returns:
            Matching Payment model instances sorted by newest first.
        """
        result = self.db.execute(
            select(Payment)
            .where(Payment.payment_provider_reference == provider_reference)
            .order_by(Payment.created_at.desc(), Payment.id.desc())
        )
        return list(result.scalars().all())
