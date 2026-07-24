from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol


@dataclass(frozen=True)
class CheckoutRequest:
    """Backend-owned values used to initialize a provider checkout.

    Attributes:
        merchant_reference: Stable PlacamIA Payment aggregate reference.
        amount: Persisted backend-owned Payment amount.
        currency: Persisted canonical Payment currency.
        customer_email: Authenticated customer email available to adapters.
        return_url: Deployment-approved customer navigation URL.
        expires_at: Backend-owned deadline for starting a provider transaction.
    """

    merchant_reference: str
    amount: Decimal
    currency: str
    customer_email: str
    return_url: str
    expires_at: datetime | None


@dataclass(frozen=True)
class RedirectCheckoutHandoff:
    """Normalized redirect handoff returned to a payment customer."""

    type: Literal["redirect"]
    url: str


@dataclass(frozen=True)
class CheckoutSession:
    """Normalized provider checkout initialization result."""

    merchant_reference: str
    provider_checkout_reference: str | None
    handoff: RedirectCheckoutHandoff
    expires_at: datetime | None


class PaymentProviderGateway(Protocol):
    """Provider mechanics required by the checkout initialization use case."""

    async def initialize_checkout(
        self,
        request: CheckoutRequest,
    ) -> CheckoutSession:
        """Return a normalized customer handoff for backend-owned values."""
