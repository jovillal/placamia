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
from app.repositories.payment_webhook_event_repository import (
    PaymentWebhookEventRepository,
)
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


def test_payment_repository_creates_and_lists_payments_by_provider_reference():
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
        assert repository.get_payments_by_provider_reference("pay-attempt-2") == [
            newer_payment
        ]
        assert repository.get_payments_by_provider_reference("missing-ref") == []
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

        assert [
            payment.payment_provider_reference for payment in payments_for_order
        ] == [
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
        assert repository.get_payments_by_provider_reference("pay-staged") == []
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


def test_payment_model_rejects_duplicate_provider_reference_for_same_order():
    db = build_session()
    try:
        customer = create_customer(db)
        order = create_order(db, customer)
        db.add(
            build_payment(
                order,
                status=PaymentStatus.PENDING,
                provider_reference="pay-duplicate",
            )
        )
        db.commit()

        db.add(
            build_payment(
                order,
                status=PaymentStatus.FAILED,
                provider_reference="pay-duplicate",
            )
        )

        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()


def test_payment_model_allows_same_provider_reference_for_different_orders():
    db = build_session()
    try:
        first_customer = create_customer(db, email="first@example.com")
        second_customer = create_customer(db, email="second@example.com")
        first_order = create_order(db, first_customer)
        second_order = create_order(db, second_customer)
        db.add_all(
            [
                build_payment(
                    first_order,
                    status=PaymentStatus.PENDING,
                    provider_reference="pay-shared",
                ),
                build_payment(
                    second_order,
                    status=PaymentStatus.PENDING,
                    provider_reference="pay-shared",
                ),
            ]
        )
        db.commit()

        assert len(db.query(Payment).all()) == 2
    finally:
        db.close()


def test_payment_webhook_event_repository_creates_and_reads_replay_key():
    db = build_session()
    try:
        customer = create_customer(db)
        order = create_order(db, customer)
        payment = build_payment(
            order,
            status=PaymentStatus.VERIFIED,
            provider_reference="pay-webhook-event",
            verified_at=datetime(2026, 6, 18, tzinfo=UTC),
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        repository = PaymentWebhookEventRepository(db)

        event = repository.create_event(
            event_id="evt-webhook-1",
            source="payment_provider_webhook",
            order_id=order.id,
            payment_id=payment.id,
        )
        db.commit()

        stored_event = repository.get_event_by_event_id("evt-webhook-1")
        assert stored_event == event
        assert stored_event.source == "payment_provider_webhook"
        assert stored_event.order_id == order.id
        assert stored_event.payment_id == payment.id
        assert stored_event.received_at is not None
    finally:
        db.close()


def test_payment_webhook_event_model_rejects_duplicate_event_id():
    db = build_session()
    try:
        customer = create_customer(db)
        order = create_order(db, customer)
        repository = PaymentWebhookEventRepository(db)
        repository.create_event(
            event_id="evt-duplicate",
            source="payment_provider_webhook",
            order_id=order.id,
        )
        db.commit()

        with pytest.raises(IntegrityError):
            repository.create_event(
                event_id="evt-duplicate",
                source="payment_provider_webhook",
                order_id=order.id,
            )
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

        webhook_event_columns = {
            column["name"]
            for column in inspect(db.bind).get_columns("payment_webhook_events")
        }
        assert webhook_event_columns == {
            "id",
            "event_id",
            "source",
            "order_id",
            "payment_id",
            "received_at",
        }
    finally:
        db.close()
