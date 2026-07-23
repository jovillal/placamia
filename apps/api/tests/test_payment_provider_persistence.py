from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.database import Base
from app.domain.order_lifecycle import OrderStatus
from app.domain.payment_lifecycle import PaymentStatus
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_provider_event import PaymentProviderEvent
from app.models.payment_provider_transaction import PaymentProviderTransaction
from app.models.user import User
from app.repositories.payment_provider_event_repository import (
    PaymentProviderEventRepository,
)
from app.repositories.payment_provider_transaction_repository import (
    PaymentProviderTransactionRepository,
)
from app.repositories.payment_repository import PaymentRepository
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_session() -> Session:
    """Build an isolated database session for provider persistence tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    return testing_session_local()


def seed_order(db: Session, *, email: str = "buyer@example.com") -> Order:
    """Persist one draft Order for Payment provider persistence tests."""
    customer = User(email=email, full_name="Provider Persistence Buyer")
    order = Order(
        customer=customer,
        status=OrderStatus.DRAFT.value,
        subtotal_amount=Decimal("50.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("9.50"),
        total_amount=Decimal("59.50"),
        currency="COP",
        assigned_provider_id="fulfillment-provider",
        terms_policy_version="terms-v1",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def seed_payment(
    db: Session,
    order: Order,
    *,
    provider_code: str,
    merchant_reference: str,
) -> Payment:
    """Persist one Payment aggregate with explicit provider identity."""
    payment = Payment(
        order_id=order.id,
        provider_code=provider_code,
        merchant_reference=merchant_reference,
        status=PaymentStatus.PENDING.value,
        amount=order.total_amount,
        currency=order.currency,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def test_payment_persists_provider_identity_and_optional_checkout_fields():
    db = build_session()
    try:
        order = seed_order(db)
        expires_at = datetime(2026, 7, 22, 18, 30, tzinfo=UTC)
        payment = Payment(
            order_id=order.id,
            provider_code="wompi",
            merchant_reference="placamia-payment-1",
            provider_checkout_reference=None,
            checkout_expires_at=expires_at,
            status=PaymentStatus.INITIATED.value,
            amount=Decimal("59.50"),
            currency="COP",
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        assert payment.provider_code == "wompi"
        assert payment.merchant_reference == "placamia-payment-1"
        assert payment.provider_checkout_reference is None
        assert payment.checkout_expires_at.replace(tzinfo=UTC) == expires_at
    finally:
        db.close()


def test_payment_repository_reads_provider_scoped_merchant_identity():
    db = build_session()
    try:
        first_order = seed_order(db, email="first@example.com")
        second_order = seed_order(db, email="second@example.com")
        wompi_payment = seed_payment(
            db,
            first_order,
            provider_code="wompi",
            merchant_reference="shared-reference",
        )
        other_payment = seed_payment(
            db,
            second_order,
            provider_code="other_provider",
            merchant_reference="shared-reference",
        )
        repository = PaymentRepository(db)

        assert (
            repository.get_payment_by_provider_identity(
                "wompi",
                "shared-reference",
            )
            == wompi_payment
        )
        assert (
            repository.get_payment_by_provider_identity(
                "other_provider",
                "shared-reference",
            )
            == other_payment
        )
        assert (
            repository.get_payment_by_provider_identity(
                "wompi",
                "missing",
            )
            is None
        )
    finally:
        db.close()


def test_payment_provider_transaction_repository_preserves_retry_history():
    db = build_session()
    try:
        order = seed_order(db)
        payment = seed_payment(
            db,
            order,
            provider_code="wompi",
            merchant_reference="placamia-payment-1",
        )
        repository = PaymentProviderTransactionRepository(db)
        first = repository.create_transaction(
            payment=payment,
            provider_transaction_reference="wompi-transaction-a",
            provider_status="DECLINED",
            normalized_status=PaymentStatus.REQUIRES_ACTION.value,
            amount=Decimal("59.50"),
            currency="COP",
            provider_created_at=datetime(2026, 7, 22, 18, 0, tzinfo=UTC),
        )
        second = repository.create_transaction(
            payment=payment,
            provider_transaction_reference="wompi-transaction-b",
            provider_status="APPROVED",
            normalized_status=PaymentStatus.VERIFIED.value,
            amount=Decimal("59.50"),
            currency="COP",
            provider_created_at=datetime(2026, 7, 22, 18, 2, tzinfo=UTC),
        )
        db.commit()

        assert (
            repository.get_transaction_by_provider_identity(
                "wompi",
                "wompi-transaction-a",
            )
            == first
        )
        assert repository.list_transactions_for_payment(payment.id) == [first, second]
        assert first.provider_code == payment.provider_code
        assert second.provider_code == payment.provider_code
        assert first.provider_transaction_reference != (
            second.provider_transaction_reference
        )
    finally:
        db.close()


def test_payment_provider_event_repository_stores_safe_independent_identity():
    db = build_session()
    try:
        order = seed_order(db)
        payment = seed_payment(
            db,
            order,
            provider_code="wompi",
            merchant_reference="placamia-payment-1",
        )
        transaction_repository = PaymentProviderTransactionRepository(db)
        transaction = transaction_repository.create_transaction(
            payment=payment,
            provider_transaction_reference="wompi-transaction-a",
            provider_status="PENDING",
            normalized_status=PaymentStatus.PENDING.value,
            amount=Decimal("59.50"),
            currency="COP",
            provider_created_at=datetime(2026, 7, 22, 18, 0, tzinfo=UTC),
        )
        event_repository = PaymentProviderEventRepository(db)
        linked_event = event_repository.create_event(
            payment=payment,
            payment_provider_transaction=transaction,
            provider_event_reference="event-reference-1",
            payload_hash="a" * 64,
            provider_occurred_at=datetime(2026, 7, 22, 18, 1, tzinfo=UTC),
        )
        unlinked_event = event_repository.create_event(
            payment=payment,
            payment_provider_transaction=None,
            provider_event_reference="event-reference-2",
            payload_hash="b" * 64,
            provider_occurred_at=None,
        )
        db.commit()

        assert (
            event_repository.get_event_by_provider_identity(
                "wompi",
                "event-reference-1",
            )
            == linked_event
        )
        assert linked_event.payload_hash == "a" * 64
        assert linked_event.provider_event_reference != linked_event.payload_hash
        assert linked_event.payment_provider_transaction_id == transaction.id
        assert unlinked_event.payment_provider_transaction_id is None
        assert event_repository.list_events_for_payment(payment.id) == [
            linked_event,
            unlinked_event,
        ]
    finally:
        db.close()


@pytest.mark.parametrize(
    ("model_factory", "expected_constraint"),
    [
        (
            lambda payment: Payment(
                order_id=payment.order_id,
                provider_code=payment.provider_code,
                merchant_reference=payment.merchant_reference,
                status=PaymentStatus.INITIATED.value,
                amount=payment.amount,
                currency=payment.currency,
            ),
            "payment",
        ),
        (
            lambda payment: PaymentProviderTransaction(
                payment_id=payment.id,
                provider_code=payment.provider_code,
                provider_transaction_reference="duplicate-transaction",
                provider_status="PENDING",
                normalized_status=PaymentStatus.PENDING.value,
                amount=payment.amount,
                currency=payment.currency,
            ),
            "transaction",
        ),
        (
            lambda payment: PaymentProviderEvent(
                payment_id=payment.id,
                provider_code=payment.provider_code,
                provider_event_reference="duplicate-event",
                payload_hash="c" * 64,
            ),
            "event",
        ),
    ],
)
def test_provider_scoped_identity_rejects_duplicates(
    model_factory,
    expected_constraint,
):
    db = build_session()
    try:
        order = seed_order(db)
        payment = seed_payment(
            db,
            order,
            provider_code="wompi",
            merchant_reference="duplicate-payment",
        )
        if expected_constraint == "payment":
            duplicate = model_factory(payment)
            duplicate.order_id = seed_order(db, email="third@example.com").id
        else:
            first = model_factory(payment)
            db.add(first)
            db.commit()
            duplicate = model_factory(payment)
        db.add(duplicate)

        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()


def test_provider_history_tables_expose_only_approved_safe_columns():
    db = build_session()
    try:
        inspector = inspect(db.bind)
        assert {column["name"] for column in inspector.get_columns("payments")} == {
            "id",
            "order_id",
            "provider_code",
            "merchant_reference",
            "provider_checkout_reference",
            "status",
            "amount",
            "currency",
            "checkout_expires_at",
            "payment_provider_reference",
            "verified_at",
            "created_at",
            "updated_at",
        }
        assert {
            column["name"]
            for column in inspector.get_columns("payment_provider_transactions")
        } == {
            "id",
            "payment_id",
            "provider_code",
            "provider_transaction_reference",
            "provider_status",
            "normalized_status",
            "amount",
            "currency",
            "provider_created_at",
            "last_observed_at",
        }
        assert {
            column["name"]
            for column in inspector.get_columns("payment_provider_events")
        } == {
            "id",
            "payment_id",
            "payment_provider_transaction_id",
            "provider_code",
            "provider_event_reference",
            "payload_hash",
            "provider_occurred_at",
            "received_at",
        }
    finally:
        db.close()
