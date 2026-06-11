from pydantic import BaseModel


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
