from app.api.dependencies import (
    get_current_user,
    get_payment_provider_runtime_factory,
    get_provider_adapter,
)
from app.core.config import settings
from app.core.database import get_db
from app.domain.payment_lifecycle import PaymentStatus
from app.domain.provider_adapter import ProviderAdapter
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.payment_webhook_event_repository import (
    PaymentWebhookEventRepository,
)
from app.schemas.payment import (
    PaymentInitializationData,
    PaymentInitializationRequest,
    PaymentInitializationResponse,
    PaymentRedirectHandoff,
    PaymentWebhookResponse,
)
from app.services.paid_order_handoff_orchestration_service import (
    PaidOrderHandoffOrchestrationService,
)
from app.services.payment_initialization_service import (
    PaymentInitializationRejected,
    PaymentInitializationService,
)
from app.services.payment_provider_registry import PaymentProviderRuntimeFactory
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
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "",
    response_model=PaymentInitializationResponse,
    summary="Initialize payment",
    description=(
        "Creates or reuses a signed Wompi Web Checkout redirect for an "
        "authenticated customer's eligible draft Order. Ownership, amount, "
        "currency, provider, merchant reference, expiration, return URL, and "
        "signature inputs are backend-owned. Initialization never verifies "
        "payment or confirms the Order."
    ),
    responses={
        201: {
            "model": PaymentInitializationResponse,
            "description": "New Wompi checkout created",
        },
        400: {"description": "Payment initialization rejected"},
        401: {"description": "Authentication required"},
        404: {"description": "Order not found for authenticated user"},
        409: {"description": "Existing Payment cannot be initialized"},
        503: {"description": "Payment provider unavailable"},
    },
)
async def initialize_payment(
    payload: PaymentInitializationRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider_adapter: ProviderAdapter = Depends(get_provider_adapter),
    payment_provider_runtime_factory: PaymentProviderRuntimeFactory = Depends(
        get_payment_provider_runtime_factory
    ),
) -> PaymentInitializationResponse:
    """Create or reuse a backend-owned hosted checkout for a draft Order.

    Args:
        payload: Strict request containing only the Order identifier.
        response: FastAPI response used to report 201 for newly created
            Payment attempts and 200 for idempotent active attempts.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        current_user: Authenticated user resolved from the bearer token.
        provider_adapter: Provider adapter dependency used only to revalidate
            current direct-checkout eligibility and priceability.
        payment_provider_runtime_factory: Lazy validated payment-provider
            registry and application checkout configuration.

    Returns:
        Customer-safe redirect handoff plus backend-owned Payment metadata.

    Side effects:
        Locks the owner-scoped Order until commit/rollback. It may expire one
        stale restartable checkout and creates at most one `requires_action`
        Wompi Payment only after local handoff construction. It never stores
        card data, verifies Payment, confirms the Order, or triggers
        fulfillment-provider handoff.

    Raises:
        HTTPException: When authentication, ownership, request shape, Order
            eligibility, or existing Payment state validation rejects the
            request.
    """
    service = PaymentInitializationService(
        OrderRepository(db),
        PaymentRepository(db),
        provider_adapter,
        payment_provider_runtime_factory,
    )

    try:
        result = await service.initialize_payment(
            order_id=payload.order_id,
            current_user=current_user,
        )
        db.commit()
    except PaymentInitializationRejected as exc:
        db.rollback()
        raise _payment_initialization_rejection(exc) from exc

    if result.created:
        response.status_code = status.HTTP_201_CREATED

    return PaymentInitializationResponse(
        data=PaymentInitializationData(
            payment_id=result.payment.id,
            order_id=result.order.id,
            payment_status=result.payment.status,
            amount=result.payment.amount,
            currency=result.payment.currency,
            handoff=PaymentRedirectHandoff(
                type=result.checkout_session.handoff.type,
                url=result.checkout_session.handoff.url,
            ),
            checkout_expires_at=result.checkout_session.expires_at,
        )
    )


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


def _payment_initialization_rejection(
    exc: PaymentInitializationRejected,
) -> HTTPException:
    """Return a safe HTTP error response for rejected payment initialization."""
    if exc.code == "order_not_found":
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code == "payment_provider_unavailable":
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif exc.code in {
        "payment_provider_not_routable",
        "payment_in_progress",
        "payment_state_invalid",
    }:
        status_code = status.HTTP_409_CONFLICT
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": str(exc)},
    )
