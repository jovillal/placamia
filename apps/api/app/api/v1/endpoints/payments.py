from app.core.config import settings
from app.core.database import get_db
from app.repositories.order_repository import OrderRepository
from app.schemas.payment import PaymentWebhookResponse
from app.services.payment_webhook_processing_service import (
    PaymentWebhookProcessingRejected,
    PaymentWebhookProcessingService,
)
from app.services.payment_webhook_verification_service import (
    PaymentWebhookVerificationRejected,
    PaymentWebhookVerificationService,
)
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "/webhook",
    response_model=PaymentWebhookResponse,
    summary="Process payment webhook",
    description=(
        "Verifies a provider-neutral payment webhook signature, validates the "
        "trusted payment event against backend-owned order state, and confirms "
        "an eligible draft order without triggering provider handoff."
    ),
    responses={
        400: {"description": "Payment webhook rejected"},
    },
)
async def process_payment_webhook(
    request: Request,
    x_payment_signature: str | None = Header(
        default=None,
        alias="X-Payment-Signature",
    ),
    db: Session = Depends(get_db),
) -> PaymentWebhookResponse:
    """Verify and process a payment-provider webhook.

    Args:
        request: FastAPI request used to read the exact raw webhook body.
        x_payment_signature: HMAC signature header supplied by the payment
            provider in `sha256=<hex>` format.
        db: SQLAlchemy session provided by FastAPI dependency injection.

    Returns:
        Provider-neutral webhook processing response with event and order
        correlation fields.

    Side effects:
        On first valid confirmation, writes the Order payment provider
        reference, payment verification timestamp, and `confirmed` status.
        The endpoint does not trigger provider handoff, provider acceptance, or
        fulfillment status updates.

    Raises:
        HTTPException: When signature verification or payment/order validation
            rejects the webhook.
    """
    raw_body = await request.body()
    verification_service = PaymentWebhookVerificationService(
        settings.PAYMENT_WEBHOOK_SECRET,
    )

    try:
        trusted_webhook = verification_service.verify_webhook(
            raw_body,
            x_payment_signature,
        )
        result = PaymentWebhookProcessingService(
            OrderRepository(db),
        ).process_verified_webhook(trusted_webhook)
    except PaymentWebhookVerificationRejected as exc:
        raise _webhook_rejection(exc) from exc
    except PaymentWebhookProcessingRejected as exc:
        raise _webhook_rejection(exc) from exc

    return PaymentWebhookResponse(
        event_id=result.event.event_id,
        order_id=result.order.id,
        order_status=result.order.status,
        payment_provider_reference=result.order.payment_provider_reference or "",
    )


def _webhook_rejection(
    exc: PaymentWebhookVerificationRejected | PaymentWebhookProcessingRejected,
) -> HTTPException:
    """Return a safe HTTP error response for rejected payment webhooks."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": exc.code, "message": str(exc)},
    )
