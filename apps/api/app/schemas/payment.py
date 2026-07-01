from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PaymentInitializationRequest(BaseModel):
    """Request body for provider-neutral payment initialization.

    The request accepts only the backend Order identifier. Amount, currency,
    status, ownership, role, provider reference, card data, and confirmation
    claims are intentionally forbidden by Pydantic's extra-field rejection.
    """

    model_config = ConfigDict(extra="forbid")

    order_id: int = Field(..., gt=0)


class PaymentInitializationData(BaseModel):
    """Customer-safe payment initialization response data.

    The response exposes only backend-owned identifiers, canonical status, and
    amount/currency values needed by the frontend to correlate the payment
    attempt. It does not include card data, provider secrets, raw provider
    payloads, or payment-confirmation fields.
    """

    payment_id: int
    order_id: int
    payment_status: str
    amount: Decimal
    currency: str


class PaymentInitializationResponse(BaseModel):
    """Provider-neutral response envelope for payment initialization."""

    data: PaymentInitializationData


class PaymentWebhookResponse(BaseModel):
    """Provider-neutral response for an accepted payment webhook.

    The response intentionally exposes only correlation fields that help the
    payment provider or tests confirm processing. It does not expose customer
    data, raw payloads, signatures, provider payment references, or sensitive
    payment details.
    """

    event_id: str
    order_id: int
    order_status: str
