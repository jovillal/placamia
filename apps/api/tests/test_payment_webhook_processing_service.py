from decimal import Decimal

import pytest
from app.core.database import Base
from app.domain.payment_lifecycle import PaymentEventSource
from app.models.order import Order
from app.models.payment import Payment
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.payment_webhook_event_repository import (
    PaymentWebhookEventRepository,
)
from app.services.payment_webhook_processing_service import (
    PaymentWebhookProcessingRejected,
    PaymentWebhookProcessingService,
)
from app.services.payment_webhook_verification_service import TrustedPaymentWebhook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for webhook service tests."""
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


def seed_order(db) -> Order:
    """Persist one draft order for payment webhook processing tests."""
    user = User(email="buyer@example.com", full_name="Test Buyer")
    order = Order(
        customer=user,
        status="draft",
        subtotal_amount=Decimal("40.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("40.00"),
        currency="COP",
        assigned_provider_id="local-provider",
        terms_policy_version="terms-v1",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def trusted_webhook_for_order(
    order: Order,
    *,
    payment_status: str = "verified",
    provider_reference: str = "pay_verified_123",
) -> TrustedPaymentWebhook:
    """Return a verified webhook result for one draft order."""
    return TrustedPaymentWebhook(
        event_id="evt_verified_123",
        payload={
            "id": "evt_verified_123",
            "data": {
                "order_id": order.id,
                "customer_id": order.customer_id,
                "payment_status": payment_status,
                "payment_provider_reference": provider_reference,
                "amount": "40.00",
                "currency": "COP",
            },
        },
        signature_scheme="hmac-sha256",
    )


def seed_payment(
    db,
    order: Order,
    *,
    status: str,
    provider_reference: str = "pay_transition_123",
) -> Payment:
    """Persist one Payment for webhook lifecycle transition tests."""
    payment = Payment(
        order_id=order.id,
        provider_code="legacy_generic",
        merchant_reference=f"legacy-transition-{order.id}-{provider_reference}",
        status=status,
        amount=Decimal("40.00"),
        currency="COP",
        payment_provider_reference=provider_reference,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def payment_for_reference(db, provider_reference: str) -> Payment | None:
    """Return one Payment by provider reference for service assertions."""
    return (
        db.query(Payment)
        .filter(Payment.payment_provider_reference == provider_reference)
        .one_or_none()
    )


def build_processing_service(db) -> PaymentWebhookProcessingService:
    """Return a payment webhook processor wired to test repositories."""
    return PaymentWebhookProcessingService(
        OrderRepository(db),
        PaymentRepository(db),
        PaymentWebhookEventRepository(db),
    )


def test_unsupported_payment_confirmation_source_rejects_without_order_mutation():
    db = build_session()
    try:
        order = seed_order(db)
        service = build_processing_service(db)
        service.event_source = PaymentEventSource.FRONTEND_RETURN

        with pytest.raises(PaymentWebhookProcessingRejected) as exc_info:
            service.process_verified_webhook(trusted_webhook_for_order(order))

        assert exc_info.value.code == "invalid_payment_source"
        stored_order = db.get(Order, order.id)
        assert stored_order.status == "draft"
        assert stored_order.payment_provider_reference is None
        assert stored_order.payment_verified_at is None
        assert stored_order.provider_handoff_reference is None
    finally:
        db.close()


@pytest.mark.parametrize(
    "payment_status",
    ["pending", "requires_action", "failed", "cancelled", "expired"],
)
def test_initial_non_verified_payment_statuses_persist_without_order_mutation(
    payment_status,
):
    db = build_session()
    try:
        order = seed_order(db)
        provider_reference = f"pay_{payment_status}"
        service = build_processing_service(db)

        result = service.process_verified_webhook(
            trusted_webhook_for_order(
                order,
                payment_status=payment_status,
                provider_reference=provider_reference,
            )
        )

        assert result.payment_confirmed is False
        assert result.order.status == "draft"
        assert result.payment.status == payment_status
        assert result.payment.payment_provider_reference == provider_reference
        assert result.payment.verified_at is None
        stored_order = db.get(Order, order.id)
        assert stored_order.status == "draft"
        assert stored_order.payment_provider_reference is None
        assert stored_order.payment_verified_at is None
        stored_payment = payment_for_reference(db, provider_reference)
        assert stored_payment is not None
        assert stored_payment.status == payment_status
    finally:
        db.close()


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        ("pending", "requires_action"),
        ("requires_action", "pending"),
    ],
)
def test_same_order_payment_provider_reference_updates_allowed_processing_statuses(
    current_status,
    target_status,
):
    db = build_session()
    try:
        order = seed_order(db)
        provider_reference = "pay_transition_123"
        existing_payment = seed_payment(
            db,
            order,
            status=current_status,
            provider_reference=provider_reference,
        )
        service = build_processing_service(db)

        result = service.process_verified_webhook(
            trusted_webhook_for_order(
                order,
                payment_status=target_status,
                provider_reference=provider_reference,
            )
        )

        assert result.payment_confirmed is False
        assert result.payment.id == existing_payment.id
        assert result.payment.status == target_status
        assert result.payment.verified_at is None
        stored_order = db.get(Order, order.id)
        assert stored_order.status == "draft"
        assert stored_order.payment_provider_reference is None
        assert stored_order.payment_verified_at is None
        stored_payment = db.get(Payment, existing_payment.id)
        assert stored_payment.status == target_status
    finally:
        db.close()


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        ("failed", "pending"),
        ("pending", "initiated"),
    ],
)
def test_invalid_payment_lifecycle_transition_rejects_without_mutation(
    current_status,
    target_status,
):
    db = build_session()
    try:
        order = seed_order(db)
        provider_reference = "pay_invalid_transition"
        existing_payment = seed_payment(
            db,
            order,
            status=current_status,
            provider_reference=provider_reference,
        )
        service = build_processing_service(db)

        with pytest.raises(PaymentWebhookProcessingRejected) as exc_info:
            service.process_verified_webhook(
                trusted_webhook_for_order(
                    order,
                    payment_status=target_status,
                    provider_reference=provider_reference,
                )
            )

        assert exc_info.value.code == "payment_transition_rejected"
        stored_order = db.get(Order, order.id)
        assert stored_order.status == "draft"
        assert stored_order.payment_provider_reference is None
        assert stored_order.payment_verified_at is None
        stored_payment = db.get(Payment, existing_payment.id)
        assert stored_payment.status == current_status
        assert stored_payment.verified_at is None
    finally:
        db.close()
