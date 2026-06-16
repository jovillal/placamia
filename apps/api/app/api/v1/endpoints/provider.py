from app.api.dependencies import get_provider_adapter, require_admin_user
from app.core.database import get_db
from app.domain.provider_adapter import ProviderAdapter
from app.models.user import User
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.provider import (
    ProviderAcceptanceDecisionRequest,
    ProviderAcceptanceDecisionResponse,
    ProviderProductionProgressRequest,
    ProviderProductionProgressResponse,
    ProviderShipmentRequest,
    ProviderShipmentResponse,
)
from app.services.audit_log_service import AuditLogService
from app.services.provider_acceptance_service import (
    ProviderAcceptanceRejected,
    ProviderAcceptanceService,
)
from app.services.provider_production_progress_service import (
    PROVIDER_PRODUCTION_PROGRESS_AUDIT_ACTION,
    ProviderProductionProgressRejected,
    ProviderProductionProgressService,
)
from app.services.provider_shipment_service import (
    PROVIDER_SHIPMENT_AUDIT_ACTION,
    ProviderShipmentRejected,
    ProviderShipmentService,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/provider", tags=["provider"])


@router.post(
    "/orders/{order_id}/acceptance",
    response_model=ProviderAcceptanceDecisionResponse,
    summary="Record provider acceptance decision",
    description=(
        "Records a backend-owned provider acceptance or rejection decision for "
        "an order already sent through the provider adapter. The endpoint "
        "requires admin authorization, calls the provider adapter boundary, "
        "does not trust customer/frontend status or reason claims, and does "
        "not mutate payment verification fields."
    ),
    responses={
        400: {"description": "Provider decision rejected"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Order not found"},
    },
)
async def record_provider_acceptance_decision(
    order_id: int,
    request: ProviderAcceptanceDecisionRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user),
    provider_adapter: ProviderAdapter = Depends(get_provider_adapter),
) -> ProviderAcceptanceDecisionResponse:
    """Record a provider acceptance/rejection decision for one order.

    Args:
        order_id: Order identifier from the route path.
        request: Provider decision body containing only the backend-owned
            decision to record.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        admin_user: Authenticated admin user authorizing this ingestion action.
        provider_adapter: Provider adapter dependency used to record the
            provider decision.

    Returns:
        Customer-safe provider decision response without payment, customer, or
        internal provider details.

    Side effects:
        May update order lifecycle status to `accepted` or `cancelled` after
        adapter validation. Commits the order update and audit log together so
        the provider decision is never persisted without audit context.

    Raises:
        HTTPException: When authorization, order lookup, lifecycle validation,
        or adapter response validation rejects the request.
    """
    service = ProviderAcceptanceService(
        OrderRepository(db),
        provider_adapter,
    )

    try:
        result = service.process_provider_decision(order_id, request.decision)
    except ProviderAcceptanceRejected as exc:
        http_status = (
            status.HTTP_404_NOT_FOUND
            if exc.code == "order_not_found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=http_status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    try:
        AuditLogService(AuditLogRepository(db)).record_admin_action(
            actor=admin_user,
            action="provider.acceptance_decision.record",
            resource_type="order",
            resource_id=result.order.id,
            event_details={
                "decision": result.decision.value,
                "order_status": result.order.status,
                "idempotent": result.idempotent,
                "customer_safe_status": result.customer_safe_status.value,
                "customer_safe_reason_code": result.customer_safe_reason_code,
            },
        )
        db.commit()
        db.refresh(result.order)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "provider_decision_audit_failed",
                "message": "Provider decision audit logging failed.",
            },
        ) from exc

    return ProviderAcceptanceDecisionResponse(
        order_id=result.order.id,
        order_status=result.order.status,
        provider_decision=result.decision,
        customer_safe_status=result.customer_safe_status.value,
        customer_safe_reason_code=result.customer_safe_reason_code,
        idempotent=result.idempotent,
    )


@router.post(
    "/orders/{order_id}/production-progress",
    response_model=ProviderProductionProgressResponse,
    summary="Record provider production progress",
    description=(
        "Records an admin-ingested provider production progress event for an "
        "order already accepted by the provider. The endpoint requires admin "
        "authorization, validates lifecycle transitions, rejects customer or "
        "frontend status claims, stores minimal transition metadata in the "
        "admin audit log, and does not mutate payment verification fields."
    ),
    responses={
        400: {"description": "Production progress rejected"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Order not found"},
    },
)
async def record_provider_production_progress(
    order_id: int,
    request: ProviderProductionProgressRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user),
) -> ProviderProductionProgressResponse:
    """Record a production progress event for one provider order.

    Args:
        order_id: Order identifier from the route path.
        request: Production progress body containing only backend-owned event
            data accepted for MVP admin ingestion.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        admin_user: Authenticated admin user authorizing this ingestion action.

    Returns:
        Customer-safe production progress response without payment, customer,
        or internal provider details.

    Side effects:
        May update order lifecycle status to `in_production` or
        `ready_for_pickup` after lifecycle validation. Commits the order update
        and audit log together so production progress is never persisted
        without audit context.

    Raises:
        HTTPException: When authorization, order lookup, lifecycle validation,
        event-reference validation, or audit persistence rejects the request.
    """
    audit_log_repository = AuditLogRepository(db)
    service = ProviderProductionProgressService(
        OrderRepository(db),
        audit_log_repository,
    )

    try:
        result = service.process_production_progress(
            order_id,
            request.event,
            event_reference=request.event_reference,
        )
    except ProviderProductionProgressRejected as exc:
        http_status = (
            status.HTTP_404_NOT_FOUND
            if exc.code == "order_not_found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=http_status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    try:
        AuditLogService(audit_log_repository).record_admin_action(
            actor=admin_user,
            action=PROVIDER_PRODUCTION_PROGRESS_AUDIT_ACTION,
            resource_type="order",
            resource_id=result.order.id,
            event_details={
                "event": result.event.value,
                "event_reference": result.event_reference,
                "from_status": result.from_status.value,
                "target_status": result.target_status.value,
                "order_status": result.order.status,
                "trigger": result.trigger.value,
                "source": "admin_ingested",
                "actor_type": "admin",
                "idempotent": result.idempotent,
            },
        )
        db.commit()
        db.refresh(result.order)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "provider_production_progress_audit_failed",
                "message": "Provider production progress audit logging failed.",
            },
        ) from exc

    return ProviderProductionProgressResponse(
        order_id=result.order.id,
        order_status=result.order.status,
        production_event=result.event,
        customer_safe_status=result.order.status,
        event_reference=result.event_reference,
        idempotent=result.idempotent,
    )


@router.post(
    "/orders/{order_id}/shipment",
    response_model=ProviderShipmentResponse,
    summary="Record provider shipment",
    description=(
        "Records an admin-ingested provider shipment event for an order ready "
        "for pickup. The endpoint requires admin authorization for both MVP QR "
        "pickup ingestion and fallback shipment events, validates lifecycle "
        "transitions, rejects customer or frontend status claims, stores "
        "minimal transition metadata in the admin audit log, and does not "
        "mutate payment verification fields."
    ),
    responses={
        400: {"description": "Shipment rejected"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Order not found"},
    },
)
async def record_provider_shipment(
    order_id: int,
    request: ProviderShipmentRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user),
) -> ProviderShipmentResponse:
    """Record a shipment event for one provider order.

    Args:
        order_id: Order identifier from the route path.
        request: Shipment body containing only backend-owned event data
            accepted for MVP admin ingestion.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        admin_user: Authenticated admin user authorizing this ingestion action.

    Returns:
        Customer-safe shipment response without payment, customer, carrier, or
        internal provider details.

    Side effects:
        May update order lifecycle status to `shipped` after lifecycle
        validation. Commits the order update and audit log together so shipment
        is never persisted without audit context.

    Raises:
        HTTPException: When authorization, order lookup, lifecycle validation,
        event-reference validation, or audit persistence rejects the request.
    """
    audit_log_repository = AuditLogRepository(db)
    service = ProviderShipmentService(
        OrderRepository(db),
        audit_log_repository,
    )

    try:
        result = service.process_shipment(
            order_id,
            request.event,
            event_reference=request.event_reference,
        )
    except ProviderShipmentRejected as exc:
        http_status = (
            status.HTTP_404_NOT_FOUND
            if exc.code == "order_not_found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=http_status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    try:
        AuditLogService(audit_log_repository).record_admin_action(
            actor=admin_user,
            action=PROVIDER_SHIPMENT_AUDIT_ACTION,
            resource_type="order",
            resource_id=result.order.id,
            event_details={
                "event": result.event.value,
                "event_reference": result.event_reference,
                "from_status": result.from_status.value,
                "target_status": result.target_status.value,
                "order_status": result.order.status,
                "trigger": result.trigger.value,
                "source": "admin_ingested",
                "actor_type": "admin",
                "idempotent": result.idempotent,
            },
        )
        db.commit()
        db.refresh(result.order)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "provider_shipment_audit_failed",
                "message": "Provider shipment audit logging failed.",
            },
        ) from exc

    return ProviderShipmentResponse(
        order_id=result.order.id,
        order_status=result.order.status,
        shipment_event=result.event,
        customer_safe_status=result.order.status,
        event_reference=result.event_reference,
        idempotent=result.idempotent,
    )
