from app.core.config import settings
from app.api.dependencies import get_provider_adapter
from app.core.database import get_db
from app.domain.payment_lifecycle import PaymentStatus
from app.domain.provider_adapter import ProviderAdapter
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.payment_webhook_event_repository import (
    PaymentWebhookEventRepository,
)
from app.schemas.payment import PaymentWebhookResponse
from app.services.paid_order_handoff_orchestration_service import (
    PaidOrderHandoffOrchestrationService,
)
from app.services.payment_webhook_processing_service import (
    PaymentWebhookProcessingRejected,
    PaymentWebhookProcessingService,
)
from app.services.payment_webhook_verification_service import (
    PaymentWebhookVerificationRejected,
    PaymentWebhookVerificationService,
)
from app.services.provider_handoff_payload_service import ProviderHandoffPayloadService
from app.services.provider_handoff_transmission_service import (
    ProviderHandoffTransmissionService,
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
        "trusted payment event against backend-owned order state, persists "
        "Payment state, and confirms an eligible draft order before attempting "
        "paid-order provider handoff."
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
    provider_adapter: ProviderAdapter = Depends(get_provider_adapter),
) -> PaymentWebhookResponse:
    """Verify and process a payment-provider webhook.

    Args:
        request: FastAPI request used to read the exact raw webhook body.
        x_payment_signature: HMAC signature header supplied by the payment
            provider in `sha256=<hex>` format.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        provider_adapter: Provider adapter dependency used for downstream
            paid-order handoff orchestration after successful confirmation.

    Returns:
        Provider-neutral webhook processing response with event and order
        correlation fields.

    Side effects:
        For accepted signed events, creates or updates the corresponding
        Payment record. On first valid verified confirmation, writes the Order
        payment provider reference, payment verification timestamp, and
        `confirmed` status. Then it attempts provider handoff through the
        orchestration boundary. Handoff failure does not roll back or reject
        payment confirmation. Non-verified accepted events do not trigger
        provider handoff. The endpoint does not persist provider
        acceptance/rejection or fulfillment status updates.

    Raises:
        HTTPException: When signature verification or payment/order validation
            rejects the webhook.
    """
    raw_body = await request.body()
    verification_service = PaymentWebhookVerificationService(
        settings.PAYMENT_WEBHOOK_SECRET,
    )
    order_repository = OrderRepository(db)
    payment_repository = PaymentRepository(db)
    webhook_event_repository = PaymentWebhookEventRepository(db)

    try:
        trusted_webhook = verification_service.verify_webhook(
            raw_body,
            x_payment_signature,
        )
        result = PaymentWebhookProcessingService(
            order_repository,
            payment_repository,
            webhook_event_repository,
        ).process_verified_webhook(trusted_webhook)
        db.commit()
    except PaymentWebhookVerificationRejected as exc:
        db.rollback()
        raise _webhook_rejection(exc) from exc
    except PaymentWebhookProcessingRejected as exc:
        db.rollback()
        raise _webhook_rejection(exc) from exc

    if not result.payment_confirmed:
        return PaymentWebhookResponse(
            event_id=result.event.event_id,
            order_id=result.order.id,
            order_status=result.order.status,
        )

    handoff_result = PaidOrderHandoffOrchestrationService(
        ProviderHandoffTransmissionService(
            order_repository,
            ProviderHandoffPayloadService(),
            provider_adapter,
        )
    ).orchestrate_confirmed_paid_order(
        result.order,
        PaymentStatus.VERIFIED,
    )

    return PaymentWebhookResponse(
        event_id=result.event.event_id,
        order_id=handoff_result.order.id,
        order_status=handoff_result.order.status,
    )


def _webhook_rejection(
    exc: PaymentWebhookVerificationRejected | PaymentWebhookProcessingRejected,
) -> HTTPException:
    """Return a safe HTTP error response for rejected payment webhooks."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": exc.code, "message": str(exc)},
    )
