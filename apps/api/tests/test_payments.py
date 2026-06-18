from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.database import Base
from app.domain.order_lifecycle import OrderStatus
from app.domain.payment_lifecycle import PaymentStatus
from app.models.order import Order
from app.models.payment import Payment
from app.models.user import User
from app.repositories.payment_repository import PaymentRepository
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
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


def create_customer(db, email: str = "buyer@example.com") -> User:
    customer = User(email=email, full_name="Test Buyer")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def create_order(db, customer: User) -> Order:
    order = Order(
        customer_id=customer.id,
        status=OrderStatus.DRAFT.value,
        subtotal_amount=Decimal("50.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("9.50"),
        total_amount=Decimal("59.50"),
        currency="COP",
        assigned_provider_id="local-provider",
        terms_policy_version="local-terms-v1",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def build_payment(
    order: Order,
    *,
    status: PaymentStatus = PaymentStatus.INITIATED,
    amount: Decimal = Decimal("59.50"),
    currency: str = "COP",
    provider_reference: str | None = None,
    verified_at: datetime | None = None,
) -> Payment:
    return Payment(
        order_id=order.id,
        status=status.value,
        amount=amount,
        currency=currency,
        payment_provider_reference=provider_reference,
        verified_at=verified_at,
    )


def test_payment_model_links_to_order_and_allows_multiple_payments_per_order():
    db = build_session()
    try:
        customer = create_customer(db)
        order = create_order(db, customer)

        first_payment = Payment(
            order=order,
            status=PaymentStatus.INITIATED.value,
            amount=Decimal("59.50"),
            currency="COP",
            payment_provider_reference="pay-attempt-1",
        )
        second_payment = Payment(
            order=order,
            status=PaymentStatus.FAILED.value,
            amount=Decimal("59.50"),
            currency="COP",
            payment_provider_reference="pay-attempt-2",
        )
        db.add_all([first_payment, second_payment])
        db.commit()
        db.refresh(order)
        db.refresh(first_payment)
        db.refresh(second_payment)

        assert first_payment.order == order
        assert second_payment.order == order
        assert {payment.id for payment in order.payments} == {
            first_payment.id,
            second_payment.id,
        }
    finally:
        db.close()


def test_payment_repository_creates_and_reads_payments_by_id_and_provider_reference():
    db = build_session()
    try:
        customer = create_customer(db)
        order = create_order(db, customer)
        repository = PaymentRepository(db)
        older_payment = repository.create_payment(
            build_payment(
                order,
                status=PaymentStatus.INITIATED,
                provider_reference="pay-attempt-1",
            )
        )
        newer_payment = repository.create_payment(
            build_payment(
                order,
                status=PaymentStatus.PENDING,
                provider_reference="pay-attempt-2",
            )
        )
        db.commit()

        assert repository.get_payment_by_id(older_payment.id) == older_payment
        assert repository.get_payment_by_id(999) is None
        assert (
            repository.get_payment_by_provider_reference("pay-attempt-2")
            == newer_payment
        )
        assert repository.get_payment_by_provider_reference("missing-ref") is None
    finally:
        db.close()


def test_payment_repository_lists_multiple_payments_for_order_newest_first():
    db = build_session()
    try:
        customer = create_customer(db)
        order = create_order(db, customer)
        repository = PaymentRepository(db)
        older_payment = repository.create_payment(
            build_payment(
                order,
                status=PaymentStatus.INITIATED,
                provider_reference="pay-attempt-1",
            )
        )
        newer_payment = repository.create_payment(
            build_payment(
                order,
                status=PaymentStatus.PENDING,
                provider_reference="pay-attempt-2",
            )
        )
        db.commit()

        payments_for_order = repository.get_payments_for_order(order.id)

        assert [payment.payment_provider_reference for payment in payments_for_order] == [
            "pay-attempt-2",
            "pay-attempt-1",
        ]
        assert payments_for_order == [
            newer_payment,
            older_payment,
        ]
    finally:
        db.close()


def test_payment_repository_create_payment_does_not_commit_transaction():
    db = build_session()
    try:
        customer = create_customer(db)
        order = create_order(db, customer)
        repository = PaymentRepository(db)

        staged_payment = repository.create_payment(
            build_payment(
                order,
                status=PaymentStatus.INITIATED,
                provider_reference="pay-staged",
            )
        )
        db.rollback()

        assert staged_payment.id is not None
        assert repository.get_payment_by_provider_reference("pay-staged") is None
    finally:
        db.close()


@pytest.mark.parametrize("payment_status", list(PaymentStatus))
def test_payment_model_accepts_canonical_payment_statuses(payment_status):
    db = build_session()
    try:
        customer = create_customer(db)
        order = create_order(db, customer)
        payment = build_payment(
            order,
            status=payment_status,
            provider_reference=f"pay-{payment_status.value}",
            verified_at=(
                datetime(2026, 6, 18, tzinfo=UTC)
                if payment_status is PaymentStatus.VERIFIED
                else None
            ),
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        assert payment.status == payment_status.value
    finally:
        db.close()


def test_payment_model_rejects_invalid_status_value():
    db = build_session()
    try:
        customer = create_customer(db)
        order = create_order(db, customer)
        db.add(
            build_payment(
                order,
                provider_reference="pay-invalid-status",
                verified_at=None,
                status=PaymentStatus.INITIATED,
            )
        )
        db.commit()

        db.add(
            Payment(
                order_id=order.id,
                status="banana",
                amount=Decimal("59.50"),
                currency="COP",
                payment_provider_reference="pay-banana",
            )
        )

        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()


def test_payment_table_matches_minimal_payment_safe_fields():
    db = build_session()
    try:
        payment_columns = {
            column["name"] for column in inspect(db.bind).get_columns("payments")
        }

        assert payment_columns == {
            "id",
            "order_id",
            "status",
            "amount",
            "currency",
            "payment_provider_reference",
            "verified_at",
            "created_at",
            "updated_at",
        }
    finally:
        db.close()
