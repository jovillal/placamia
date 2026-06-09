from __future__ import annotations

import hmac
import json
from collections.abc import Collection
from dataclasses import dataclass
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class PaymentWebhookVerificationRejected(ValueError):
    """Raised when payment webhook authenticity verification rejects input.

    Attributes:
        code: Stable rejection reason for routes, services, and tests.
        message: Safe human-readable explanation of the rejection.
    """

    code: str
    message: str

    def __str__(self) -> str:
        """Return the safe human-readable rejection message."""
        return self.message


@dataclass(frozen=True)
class TrustedPaymentWebhook:
    """Provider-neutral result for an authenticated payment webhook.

    Attributes:
        event_id: Provider event identifier used by later replay storage.
        payload: Decoded provider payload verified against the raw request body.
        signature_scheme: Provider-neutral signature scheme used for this
            verification result.
    """

    event_id: str
    payload: dict[str, Any]
    signature_scheme: str


class PaymentWebhookVerificationService:
    """Verify provider-neutral payment webhook signatures without side effects.

    The service authenticates the raw webhook body using a server-side
    HMAC-SHA256 secret and rejects malformed, missing, invalid, or replayed
    inputs before any payment, order, checkout, or provider handoff mutation can
    happen. It does not interpret provider-specific event types and does not
    mark payments or orders as verified.
    """

    signature_scheme = "hmac-sha256"
    signature_header_prefix = "sha256="
    signature_hex_length = 64

    def __init__(self, webhook_secret: str | None) -> None:
        """Create a payment webhook verification service.

        Args:
            webhook_secret: Server-side secret used to authenticate webhook
                request bodies. The secret must come from backend
                configuration, not frontend input.

        Returns:
            None.

        Side effects:
            Stores the secret for later verification.
        """
        self.webhook_secret = webhook_secret

    def verify_webhook(
        self,
        raw_body: bytes,
        signature_header: str | None,
        *,
        processed_event_ids: Collection[str] | None = None,
    ) -> TrustedPaymentWebhook:
        """Verify a raw payment webhook request and return a trusted result.

        Args:
            raw_body: Exact raw request body bytes received from the provider.
            signature_header: Signature header value in `sha256=<hex>` format.
            processed_event_ids: Optional caller-owned set of event ids that
                have already been processed by replay/idempotency storage.

        Returns:
            A provider-neutral trusted webhook result for later payment
            processing.

        Raises:
            PaymentWebhookVerificationRejected: If configuration, signature,
                payload, event id, or replay validation fails.

        Side effects:
            None. The service only validates input and returns a trusted result.
            It never mutates payment, order, checkout, or provider handoff
            state, and it never records replay keys itself.
        """
        secret = self._require_webhook_secret()
        provided_signature = self._parse_signature_header(signature_header)
        expected_signature = self._sign(raw_body, secret)

        if not hmac.compare_digest(provided_signature, expected_signature):
            raise PaymentWebhookVerificationRejected(
                code="invalid_signature",
                message="Payment webhook signature is invalid.",
            )

        payload = self._decode_payload(raw_body)
        event_id = self._extract_event_id(payload)
        self._reject_replayed_event(event_id, processed_event_ids)

        return TrustedPaymentWebhook(
            event_id=event_id,
            payload=payload,
            signature_scheme=self.signature_scheme,
        )

    def _require_webhook_secret(self) -> str:
        """Return the configured webhook secret.

        Returns:
            Configured payment webhook secret.

        Raises:
            PaymentWebhookVerificationRejected: If no secret is configured.

        Side effects:
            None.
        """
        if not self.webhook_secret:
            raise PaymentWebhookVerificationRejected(
                code="webhook_secret_not_configured",
                message="Payment webhook verification is not configured.",
            )

        return self.webhook_secret

    def _parse_signature_header(self, signature_header: str | None) -> str:
        """Parse and normalize the payment webhook signature header.

        Args:
            signature_header: Raw signature header value from the request.

        Returns:
            Normalized lower-case hexadecimal HMAC digest.

        Raises:
            PaymentWebhookVerificationRejected: If the header is missing or
                malformed.

        Side effects:
            None.
        """
        if signature_header is None or not signature_header.strip():
            raise PaymentWebhookVerificationRejected(
                code="missing_signature",
                message="Payment webhook signature is required.",
            )

        header = signature_header.strip()
        if not header.startswith(self.signature_header_prefix):
            raise PaymentWebhookVerificationRejected(
                code="malformed_signature",
                message="Payment webhook signature is malformed.",
            )

        signature = header[len(self.signature_header_prefix) :].strip().lower()
        if len(signature) != self.signature_hex_length:
            raise PaymentWebhookVerificationRejected(
                code="malformed_signature",
                message="Payment webhook signature is malformed.",
            )

        try:
            int(signature, 16)
        except ValueError as exc:
            raise PaymentWebhookVerificationRejected(
                code="malformed_signature",
                message="Payment webhook signature is malformed.",
            ) from exc

        return signature

    def _decode_payload(self, raw_body: bytes) -> dict[str, Any]:
        """Decode a verified payment webhook body into a JSON object.

        Args:
            raw_body: Exact raw request body bytes received from the provider.

        Returns:
            Decoded JSON object payload.

        Raises:
            PaymentWebhookVerificationRejected: If the body is not UTF-8 JSON
                or the decoded JSON value is not an object.

        Side effects:
            None.
        """
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PaymentWebhookVerificationRejected(
                code="malformed_payload",
                message="Payment webhook payload is malformed.",
            ) from exc

        if not isinstance(payload, dict):
            raise PaymentWebhookVerificationRejected(
                code="malformed_payload",
                message="Payment webhook payload is malformed.",
            )

        return payload

    def _extract_event_id(self, payload: dict[str, Any]) -> str:
        """Extract the provider-neutral event id from a verified payload.

        Args:
            payload: Decoded payment webhook JSON object.

        Returns:
            Non-empty provider event id.

        Raises:
            PaymentWebhookVerificationRejected: If the payload lacks an id.

        Side effects:
            None.
        """
        raw_event_id = payload.get("id", payload.get("event_id"))
        if not isinstance(raw_event_id, str) or not raw_event_id.strip():
            raise PaymentWebhookVerificationRejected(
                code="missing_event_id",
                message="Payment webhook event id is required.",
            )

        return raw_event_id.strip()

    def _reject_replayed_event(
        self,
        event_id: str,
        processed_event_ids: Collection[str] | None,
    ) -> None:
        """Reject events already present in caller-owned idempotency storage.

        Args:
            event_id: Verified provider event id.
            processed_event_ids: Optional processed event id collection.

        Raises:
            PaymentWebhookVerificationRejected: If the event id was already
                processed.

        Side effects:
            None. The caller owns persistence for replay keys.
        """
        if processed_event_ids is not None and event_id in processed_event_ids:
            raise PaymentWebhookVerificationRejected(
                code="replayed_event",
                message="Payment webhook event has already been processed.",
            )

    @staticmethod
    def _sign(raw_body: bytes, secret: str) -> str:
        """Sign a raw webhook body with HMAC-SHA256.

        Args:
            raw_body: Exact raw request body bytes.
            secret: Server-side payment webhook secret.

        Returns:
            Hex-encoded HMAC-SHA256 signature.

        Side effects:
            None.
        """
        return hmac.new(secret.encode(), raw_body, sha256).hexdigest()
