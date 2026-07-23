from datetime import datetime
from decimal import Decimal

from app.models.payment import Payment
from app.models.payment_provider_transaction import PaymentProviderTransaction
from sqlalchemy import select
from sqlalchemy.orm import Session


class PaymentProviderTransactionRepository:
    """Persist and read safe external transaction observations."""

    def __init__(self, db: Session) -> None:
        """Store the caller-owned database session."""
        self.db = db

    def create_transaction(
        self,
        *,
        payment: Payment,
        provider_transaction_reference: str,
        provider_status: str,
        normalized_status: str,
        amount: Decimal,
        currency: str,
        provider_created_at: datetime | None,
    ) -> PaymentProviderTransaction:
        """Stage one provider transaction linked to a Payment aggregate.

        Args:
            payment: Persisted owning Payment whose provider code is canonical.
            provider_transaction_reference: Provider transaction identifier.
            provider_status: Exact safe provider status label.
            normalized_status: Canonical PlacamIA payment observation status.
            amount: Provider-observed transaction amount.
            currency: Provider-observed ISO currency code.
            provider_created_at: Provider transaction creation time when known.

        Returns:
            The staged safe transaction observation.

        Side effects:
            Flushes one transaction row in the caller-owned transaction without
            committing it.
        """
        transaction = PaymentProviderTransaction(
            payment_id=payment.id,
            provider_code=payment.provider_code,
            provider_transaction_reference=provider_transaction_reference,
            provider_status=provider_status,
            normalized_status=normalized_status,
            amount=amount,
            currency=currency,
            provider_created_at=provider_created_at,
        )
        self.db.add(transaction)
        self.db.flush()
        self.db.refresh(transaction)
        return transaction

    def get_transaction_by_provider_identity(
        self,
        provider_code: str,
        provider_transaction_reference: str,
    ) -> PaymentProviderTransaction | None:
        """Return one transaction by provider-scoped external identity."""
        return self.db.scalar(
            select(PaymentProviderTransaction).where(
                PaymentProviderTransaction.provider_code == provider_code,
                PaymentProviderTransaction.provider_transaction_reference
                == provider_transaction_reference,
            )
        )

    def list_transactions_for_payment(
        self,
        payment_id: int,
    ) -> list[PaymentProviderTransaction]:
        """Return all transaction observations for one Payment in id order."""
        result = self.db.execute(
            select(PaymentProviderTransaction)
            .where(PaymentProviderTransaction.payment_id == payment_id)
            .order_by(PaymentProviderTransaction.id.asc())
        )
        return list(result.scalars().all())
