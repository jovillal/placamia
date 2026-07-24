from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from urllib.parse import urlencode

from app.domain.payment_provider_gateway import (
    CheckoutRequest,
    CheckoutSession,
    RedirectCheckoutHandoff,
)

WOMPI_CHECKOUT_URL = "https://checkout.wompi.co/p/"
COP_CENTS_MULTIPLIER = Decimal("100")


class UnsupportedPaymentCurrency(ValueError):
    """Raised when Wompi cannot initialize the persisted Payment currency."""


class InvalidPaymentAmount(ValueError):
    """Raised when a Payment amount cannot be represented as exact COP cents."""


class PaymentProviderHandoffError(RuntimeError):
    """Raised when a provider handoff cannot be constructed safely."""


class WompiPaymentProvider:
    """Construct signed Wompi Web Checkout redirect handoffs locally."""

    def __init__(
        self,
        *,
        public_key: str,
        integrity_secret: str,
        approved_return_url: str,
    ) -> None:
        """Store validated Wompi checkout configuration.

        Args:
            public_key: Environment-matched Wompi public checkout key.
            integrity_secret: Environment-matched Wompi integrity secret.
            approved_return_url: Sole deployment-approved browser return URL.

        Side effects:
            None. Configuration values are retained in memory only.
        """
        self._public_key = public_key
        self._integrity_secret = integrity_secret
        self._approved_return_url = approved_return_url

    async def initialize_checkout(
        self,
        request: CheckoutRequest,
    ) -> CheckoutSession:
        """Build a normalized Wompi hosted-checkout redirect.

        Args:
            request: Backend-owned Payment identity, amount, currency,
                expiration, customer context, and return URL.

        Returns:
            A redirect checkout session with no provider session identifier.

        Raises:
            UnsupportedPaymentCurrency: If the persisted currency is not COP.
            InvalidPaymentAmount: If the amount is non-positive or cannot be
                represented as exact integer cents.
            PaymentProviderHandoffError: If expiration or return URL does not
                match the approved checkout contract.

        Side effects:
            None. Wompi Web Checkout initialization performs no network call
            and does not persist or log the signed URL.
        """
        if request.currency != "COP":
            raise UnsupportedPaymentCurrency("Wompi checkout supports COP only.")
        if request.return_url != self._approved_return_url:
            raise PaymentProviderHandoffError(
                "Checkout return URL does not match approved configuration."
            )
        if request.expires_at is None:
            raise PaymentProviderHandoffError("Checkout expiration is required.")

        amount_in_cents = _exact_amount_in_cents(request.amount)
        normalized_expiration = _normalize_utc(request.expires_at)
        expiration_time = serialize_wompi_expiration(normalized_expiration)
        signature_preimage = (
            f"{request.merchant_reference}"
            f"{amount_in_cents}"
            f"{request.currency}"
            f"{expiration_time}"
            f"{self._integrity_secret}"
        )
        integrity_signature = sha256(signature_preimage.encode("utf-8")).hexdigest()
        query = urlencode(
            [
                ("public-key", self._public_key),
                ("currency", request.currency),
                ("amount-in-cents", str(amount_in_cents)),
                ("reference", request.merchant_reference),
                ("signature:integrity", integrity_signature),
                ("redirect-url", request.return_url),
                ("expiration-time", expiration_time),
            ]
        )
        return CheckoutSession(
            merchant_reference=request.merchant_reference,
            provider_checkout_reference=None,
            handoff=RedirectCheckoutHandoff(
                type="redirect",
                url=f"{WOMPI_CHECKOUT_URL}?{query}",
            ),
            expires_at=normalized_expiration,
        )


def _exact_amount_in_cents(amount: Decimal) -> int:
    """Return exact integer cents without rounding invalid precision."""
    amount_in_cents = amount * COP_CENTS_MULTIPLIER
    if amount <= 0 or amount_in_cents != amount_in_cents.to_integral_value():
        raise InvalidPaymentAmount(
            "Payment amount must be positive and representable as exact cents."
        )
    return int(amount_in_cents)


def serialize_wompi_expiration(expires_at: datetime) -> str:
    """Serialize one expiration instant as UTC ISO-8601 milliseconds."""
    normalized = _normalize_utc(expires_at)
    milliseconds = normalized.microsecond // 1000
    return normalized.strftime("%Y-%m-%dT%H:%M:%S.") + f"{milliseconds:03d}Z"


def _normalize_utc(value: datetime) -> datetime:
    """Return an aware UTC instant, treating persisted naive values as UTC."""
    expires_at = value
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at.astimezone(UTC)
