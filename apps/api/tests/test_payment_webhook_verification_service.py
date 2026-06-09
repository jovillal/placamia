import hmac
import json
from dataclasses import dataclass
from hashlib import sha256

import pytest
from app.core.config import Settings
from app.domain.order_lifecycle import OrderStatus
from app.domain.payment_lifecycle import PaymentStatus
from app.services.payment_webhook_verification_service import (
    PaymentWebhookVerificationRejected,
    PaymentWebhookVerificationService,
)

WEBHOOK_SECRET = "test-payment-webhook-secret"


@dataclass
class MutablePaymentRecord:
    """Tiny mutable stand-in proving verification does not mutate payment."""

    status: PaymentStatus


@dataclass
class MutableOrderRecord:
    """Tiny mutable stand-in proving verification does not mutate orders."""

    status: OrderStatus
    payment_verified_at: str | None = None


@dataclass
class MutableProviderHandoffRecord:
    """Tiny mutable stand-in proving verification does not trigger handoff."""

    handoff_count: int = 0


def raw_payload(**overrides) -> bytes:
    """Build a deterministic raw JSON payload for signature tests."""
    payload = {
        "id": "evt_test_123",
        "type": "payment.verified",
        "data": {"order_id": 1, "amount": "40.00", "currency": "COP"},
    }
    payload.update(overrides)
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def signature_header(raw_body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Return the provider-neutral test signature header for a raw payload."""
    signature = hmac.new(secret.encode(), raw_body, sha256).hexdigest()
    return f"sha256={signature}"


def assert_verification_rejection(exc_info, code: str) -> None:
    """Assert a webhook verification rejection uses a safe stable code."""
    rejection = exc_info.value
    assert rejection.code == code
    assert WEBHOOK_SECRET not in str(rejection)


def assert_no_payment_order_or_handoff_mutation(
    payment_record: MutablePaymentRecord,
    order_record: MutableOrderRecord,
    handoff_record: MutableProviderHandoffRecord,
) -> None:
    """Assert webhook verification did not mutate caller-owned records."""
    assert payment_record.status is PaymentStatus.PENDING
    assert order_record.status is OrderStatus.DRAFT
    assert order_record.payment_verified_at is None
    assert handoff_record.handoff_count == 0


def test_valid_signature_verification_returns_provider_neutral_trusted_result():
    raw_body = raw_payload()
    service = PaymentWebhookVerificationService(WEBHOOK_SECRET)
    payment_record = MutablePaymentRecord(PaymentStatus.PENDING)
    order_record = MutableOrderRecord(OrderStatus.DRAFT)
    handoff_record = MutableProviderHandoffRecord()

    trusted_webhook = service.verify_webhook(
        raw_body,
        signature_header(raw_body),
    )

    assert trusted_webhook.event_id == "evt_test_123"
    assert trusted_webhook.payload["type"] == "payment.verified"
    assert trusted_webhook.signature_scheme == "hmac-sha256"
    assert_no_payment_order_or_handoff_mutation(
        payment_record,
        order_record,
        handoff_record,
    )


def test_settings_load_payment_webhook_secret_from_environment(monkeypatch):
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", "env-payment-webhook-secret")

    settings = Settings()

    assert settings.PAYMENT_WEBHOOK_SECRET == "env-payment-webhook-secret"


def test_missing_configured_webhook_secret_is_rejected():
    raw_body = raw_payload()
    service = PaymentWebhookVerificationService(None)

    with pytest.raises(PaymentWebhookVerificationRejected) as exc_info:
        service.verify_webhook(raw_body, signature_header(raw_body))

    assert_verification_rejection(exc_info, "webhook_secret_not_configured")


def test_missing_signature_rejected_without_payment_order_or_handoff_mutation():
    raw_body = raw_payload()
    service = PaymentWebhookVerificationService(WEBHOOK_SECRET)
    payment_record = MutablePaymentRecord(PaymentStatus.PENDING)
    order_record = MutableOrderRecord(OrderStatus.DRAFT)
    handoff_record = MutableProviderHandoffRecord()

    with pytest.raises(PaymentWebhookVerificationRejected) as exc_info:
        service.verify_webhook(raw_body, None)

    assert_verification_rejection(exc_info, "missing_signature")
    assert_no_payment_order_or_handoff_mutation(
        payment_record,
        order_record,
        handoff_record,
    )


def test_invalid_signature_rejected_without_payment_order_or_handoff_mutation():
    raw_body = raw_payload()
    service = PaymentWebhookVerificationService(WEBHOOK_SECRET)
    payment_record = MutablePaymentRecord(PaymentStatus.PENDING)
    order_record = MutableOrderRecord(OrderStatus.DRAFT)
    handoff_record = MutableProviderHandoffRecord()

    with pytest.raises(PaymentWebhookVerificationRejected) as exc_info:
        service.verify_webhook(raw_body, signature_header(raw_body, "wrong-secret"))

    assert_verification_rejection(exc_info, "invalid_signature")
    assert_no_payment_order_or_handoff_mutation(
        payment_record,
        order_record,
        handoff_record,
    )


def test_malformed_signature_rejected_safely():
    raw_body = raw_payload()
    service = PaymentWebhookVerificationService(WEBHOOK_SECRET)

    with pytest.raises(PaymentWebhookVerificationRejected) as exc_info:
        service.verify_webhook(raw_body, "not-a-signature")

    assert_verification_rejection(exc_info, "malformed_signature")


def test_malformed_payload_rejected_without_payment_order_or_handoff_mutation():
    raw_body = b"{not-json"
    service = PaymentWebhookVerificationService(WEBHOOK_SECRET)
    payment_record = MutablePaymentRecord(PaymentStatus.PENDING)
    order_record = MutableOrderRecord(OrderStatus.DRAFT)
    handoff_record = MutableProviderHandoffRecord()

    with pytest.raises(PaymentWebhookVerificationRejected) as exc_info:
        service.verify_webhook(raw_body, signature_header(raw_body))

    assert_verification_rejection(exc_info, "malformed_payload")
    assert_no_payment_order_or_handoff_mutation(
        payment_record,
        order_record,
        handoff_record,
    )


def test_missing_event_id_rejected_safely():
    raw_body = raw_payload(id=None)
    service = PaymentWebhookVerificationService(WEBHOOK_SECRET)

    with pytest.raises(PaymentWebhookVerificationRejected) as exc_info:
        service.verify_webhook(raw_body, signature_header(raw_body))

    assert_verification_rejection(exc_info, "missing_event_id")


def test_replayed_event_rejected_without_confirming_order_or_payment():
    raw_body = raw_payload()
    service = PaymentWebhookVerificationService(WEBHOOK_SECRET)
    payment_record = MutablePaymentRecord(PaymentStatus.PENDING)
    order_record = MutableOrderRecord(OrderStatus.DRAFT)
    handoff_record = MutableProviderHandoffRecord()

    with pytest.raises(PaymentWebhookVerificationRejected) as exc_info:
        service.verify_webhook(
            raw_body,
            signature_header(raw_body),
            processed_event_ids={"evt_test_123"},
        )

    assert_verification_rejection(exc_info, "replayed_event")
    assert_no_payment_order_or_handoff_mutation(
        payment_record,
        order_record,
        handoff_record,
    )


def test_signed_frontend_payment_claims_do_not_mark_order_paid():
    raw_body = raw_payload(
        frontend_claims={
            "payment_status": "verified",
            "order_status": "confirmed",
            "payment_verified_at": "2026-06-09T00:00:00Z",
            "provider_handoff": True,
        }
    )
    service = PaymentWebhookVerificationService(WEBHOOK_SECRET)
    payment_record = MutablePaymentRecord(PaymentStatus.PENDING)
    order_record = MutableOrderRecord(OrderStatus.DRAFT)
    handoff_record = MutableProviderHandoffRecord()

    trusted_webhook = service.verify_webhook(raw_body, signature_header(raw_body))

    assert trusted_webhook.event_id == "evt_test_123"
    assert trusted_webhook.payload["frontend_claims"]["payment_status"] == "verified"
    assert_no_payment_order_or_handoff_mutation(
        payment_record,
        order_record,
        handoff_record,
    )


def test_verification_errors_do_not_log_secret_or_raw_payload(caplog):
    raw_body = raw_payload(data={"card_last4": "4242", "customer": "Ada"})
    service = PaymentWebhookVerificationService(WEBHOOK_SECRET)

    with pytest.raises(PaymentWebhookVerificationRejected):
        service.verify_webhook(raw_body, signature_header(raw_body, "wrong-secret"))

    assert WEBHOOK_SECRET not in caplog.text
    assert "card_last4" not in caplog.text
    assert "4242" not in caplog.text
