from decimal import Decimal

import pytest
from app.core.database import Base
from app.domain.payment_lifecycle import PaymentEventSource
from app.models.order import Order
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
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


def trusted_webhook_for_order(order: Order) -> TrustedPaymentWebhook:
    """Return a verified webhook result for one draft order."""
    return TrustedPaymentWebhook(
        event_id="evt_verified_123",
        payload={
            "id": "evt_verified_123",
            "data": {
                "order_id": order.id,
                "customer_id": order.customer_id,
                "payment_status": "verified",
                "payment_provider_reference": "pay_verified_123",
                "amount": "40.00",
                "currency": "COP",
            },
        },
        signature_scheme="hmac-sha256",
    )


def test_unsupported_payment_confirmation_source_rejects_without_order_mutation():
    db = build_session()
    try:
        order = seed_order(db)
        service = PaymentWebhookProcessingService(
            OrderRepository(db),
            PaymentRepository(db),
        )
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
