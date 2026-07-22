from app.api.dependencies import (
    get_current_user,
    get_provider_adapter,
    require_admin_user,
)
from app.core.database import get_db
from app.models.user import User
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.kit_repository import KitRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.order import (
    OrderCancellationRequest,
    OrderCancellationResolutionRequest,
    OrderCancellationResponse,
    OrderCreateRequest,
    OrderDetailItemRead,
    OrderDetailRead,
    OrderListMeta,
    OrderListResponse,
    OrderRead,
    OrderStatusRead,
    OrderSummaryRead,
)
from app.services.audit_log_service import AuditLogService
from app.services.checkout_service import CheckoutEligibilityService
from app.services.order_cancellation_service import (
    ADMIN_CANCELLATION_APPROVAL_AUDIT_ACTION,
    ADMIN_CANCELLATION_REJECTION_AUDIT_ACTION,
    CUSTOMER_CANCELLATION_REQUEST_AUDIT_ACTION,
    OrderCancellationRejected,
    OrderCancellationService,
)
from app.services.order_creation_service import OrderCreationRejected
from app.services.order_creation_service import OrderCreationService
from app.services.order_detail_service import OrderDetailService
from app.services.order_list_service import OrderListService
from app.services.pricing_service import PathAPricingService
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/orders", tags=["orders"])

ALLOWED_ORDER_LIST_QUERY_PARAMS = frozenset({"page", "page_size"})
MAX_ORDER_PAGE_SIZE = 100


@router.get(
    "",
    response_model=OrderListResponse,
    summary="List customer orders",
    description=(
        "Returns a deterministic page of persisted customer-safe Order "
        "summaries owned by the authenticated user. Supports only page and "
        "page_size and never recalculates historical totals."
    ),
    responses={
        401: {"description": "Authentication required"},
        422: {"description": "Invalid or unsupported query parameter"},
    },
)
async def list_customer_orders(
    request: Request,
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=20, gt=0, le=MAX_ORDER_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderListResponse:
    """Return one owner-scoped page of persisted Order summaries.

    Args:
        request: Incoming request used to reject unsupported query parameters.
        page: One-based page number. Defaults to 1.
        page_size: Positive page size up to 100. Defaults to 20.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        current_user: Authenticated user resolved from the bearer token.

    Returns:
        Customer-safe Order summaries and owner-scoped pagination metadata.

    Side effects:
        Reads persisted Order summary data only. The endpoint does not mutate
        orders or load customer, OrderItem, Payment, or provider details.

    Raises:
        HTTPException: When unsupported query parameters are supplied.
    """
    _reject_unsupported_order_list_query_params(request)

    result = OrderListService(OrderRepository(db)).list_customer_orders(
        customer_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return OrderListResponse(
        data=[OrderSummaryRead.model_validate(order) for order in result.orders],
        meta=OrderListMeta(
            page=result.page,
            page_size=result.page_size,
            total_items=result.total_items,
            total_pages=result.total_pages,
        ),
    )


@router.get(
    "/{order_id}",
    response_model=OrderDetailRead,
    summary="Get customer order detail",
    description=(
        "Returns one authenticated customer's persisted Order and immutable "
        "purchased-item snapshots. The response does not recalculate from or "
        "expose current catalog, Payment relationship, provider references, "
        "or internal state and accepts no query parameters."
    ),
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Order not found"},
        422: {"description": "Unsupported query parameter"},
    },
)
async def get_customer_order_detail(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderDetailRead:
    """Return customer-safe persisted detail for one owned Order.

    Args:
        order_id: Order identifier from the route path.
        request: Incoming request used to reject every query parameter.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        current_user: Authenticated user resolved from the bearer token.

    Returns:
        Customer-safe Order lifecycle, totals, timestamps, and immutable item
        snapshots read only from approved persisted columns.

    Side effects:
        Reads owner-scoped Order and OrderItem snapshots only. No persistence,
        payment, provider, catalog, or audit state is mutated.

    Raises:
        HTTPException: When query parameters are supplied or the owner-scoped
            Order does not exist.
    """
    _reject_order_detail_query_params(request)

    detail = OrderDetailService(OrderRepository(db)).get_customer_order_detail(
        order_id=order_id,
        customer_id=current_user.id,
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    order = detail.order
    return OrderDetailRead(
        id=order.id,
        status=order.status,
        currency=order.currency,
        subtotal_amount=order.subtotal_amount,
        discount_amount=order.discount_amount,
        tax_amount=order.tax_amount,
        total_amount=order.total_amount,
        payment_verified_at=order.payment_verified_at,
        provider_handoff_sent_at=order.provider_handoff_sent_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=[OrderDetailItemRead.model_validate(item) for item in detail.items],
    )


@router.get(
    "/{order_id}/status",
    response_model=OrderStatusRead,
    summary="Get order status",
    description=(
        "Returns customer-safe Path A order tracking information for the "
        "authenticated owner. Provider, payment, and internal handoff details "
        "are not exposed."
    ),
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Order not found"},
    },
)
async def get_order_status(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderStatusRead:
    """Return customer-safe status information for one owned order.

    Args:
        order_id: Order identifier from the route path.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        current_user: Authenticated user resolved from the bearer token.

    Returns:
        Customer-safe order lifecycle status and immutable item snapshots.

    Side effects:
        None. This endpoint only reads persisted order data and never mutates
        order, payment, provider, or handoff state.

    Raises:
        HTTPException: When the order is missing or not owned by current_user.
    """
    order = OrderRepository(db).get_order_for_customer(order_id, current_user.id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return OrderStatusRead.model_validate(order)


def _reject_unsupported_order_list_query_params(request: Request) -> None:
    """Reject query parameters outside the customer Order list contract."""
    unsupported_parameters = sorted(
        set(request.query_params.keys()) - ALLOWED_ORDER_LIST_QUERY_PARAMS
    )
    if unsupported_parameters:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "unsupported_query_parameter",
                "message": "Unsupported query parameter.",
                "unsupported_parameters": unsupported_parameters,
            },
        )


def _reject_order_detail_query_params(request: Request) -> None:
    """Reject every query parameter for the customer Order detail contract."""
    unsupported_parameters = sorted(set(request.query_params.keys()))
    if unsupported_parameters:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "unsupported_query_parameter",
                "message": "Unsupported query parameter.",
                "unsupported_parameters": unsupported_parameters,
            },
        )


@router.post(
    "",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create draft order",
    description=(
        "Creates a draft Path A order from backend-validated checkout state. "
        "The endpoint requires authentication, derives ownership from the "
        "current user, and does not initialize payment or provider handoff."
    ),
    responses={
        400: {"description": "Order creation request rejected"},
        401: {"description": "Authentication required"},
    },
)
async def create_draft_order(
    request: OrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider_adapter=Depends(get_provider_adapter),
) -> OrderRead:
    """Create a draft order from backend-validated checkout state.

    Args:
        request: Order creation request body containing checkout item identity,
            quantity, options, and terms acknowledgement.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        current_user: Authenticated user resolved from the bearer token.
        provider_adapter: Backend-owned provider adapter used by checkout and
            pricing validation.

    Returns:
        Persisted draft Order with immutable OrderItem snapshots.

    Side effects:
        Creates order rows only after checkout validation succeeds. The endpoint
        does not write payment verification fields, initialize payment, write
        provider handoff fields, or send provider adapter handoffs.

    Raises:
        HTTPException: When checkout or order creation validation rejects the
            request.
    """
    product_repository = ProductRepository(db)
    checkout_service = CheckoutEligibilityService(
        product_repository,
        KitRepository(db),
        PathAPricingService(provider_adapter),
    )
    order_service = OrderCreationService(
        checkout_service,
        OrderRepository(db),
    )

    try:
        order = order_service.create_draft_order(request, current_user)
    except OrderCreationRejected as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return OrderRead.model_validate(order)


@router.post(
    "/{order_id}/cancellation-request",
    response_model=OrderCancellationResponse,
    summary="Request order cancellation",
    description=(
        "Allows the authenticated owning customer to request cancellation for "
        "eligible paid orders. The request moves the order to "
        "`cancellation_requested`, preserves payment and fulfillment history, "
        "and records an audit entry. Customers cannot directly cancel orders."
    ),
    responses={
        400: {"description": "Cancellation request rejected"},
        401: {"description": "Authentication required"},
        404: {"description": "Order not found"},
    },
)
async def request_order_cancellation(
    order_id: int,
    request: OrderCancellationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderCancellationResponse:
    """Request cancellation for one authenticated customer's paid order.

    Args:
        order_id: Order identifier from the route path.
        request: Empty request body used only to reject frontend-owned status
            or authorization claims.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        current_user: Authenticated user resolved from the bearer token.

    Returns:
        Customer-safe cancellation workflow response.

    Side effects:
        May stage a transition to `cancellation_requested`, persist the prior
        paid status in `cancellation_requested_from`, and record an audit log
        in the same transaction. Payment confirmation and provider fulfillment
        history fields remain untouched.

    Raises:
        HTTPException: When the order is missing, not owned by current_user,
            or not in an eligible state.
    """
    audit_log_repository = AuditLogRepository(db)
    service = OrderCancellationService(OrderRepository(db))

    try:
        result = service.request_cancellation(order_id, customer_id=current_user.id)
    except OrderCancellationRejected as exc:
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
        AuditLogService(audit_log_repository).record_user_action(
            actor=current_user,
            action=CUSTOMER_CANCELLATION_REQUEST_AUDIT_ACTION,
            resource_type="order",
            resource_id=result.order.id,
            event_details={
                "from_status": result.from_status.value,
                "target_status": result.target_status.value,
                "order_status": result.order.status,
                "trigger": result.trigger.value,
                "cancellation_requested_from": (
                    result.cancellation_requested_from.value
                    if result.cancellation_requested_from is not None
                    else None
                ),
                "actor_type": "customer",
            },
        )
        db.commit()
        db.refresh(result.order)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "order_cancellation_audit_failed",
                "message": "Order cancellation audit logging failed.",
            },
        ) from exc

    return OrderCancellationResponse(
        order_id=result.order.id,
        order_status=result.order.status,
        cancellation_requested_from=result.order.cancellation_requested_from,
        customer_safe_status=result.order.status,
    )


@router.post(
    "/{order_id}/cancellation-request/approve",
    response_model=OrderCancellationResponse,
    summary="Approve order cancellation request",
    description=(
        "Allows an authenticated admin to approve a pending customer "
        "cancellation request. Approval moves the order to `cancelled`, "
        "preserves payment and fulfillment history, and records an audit "
        "entry."
    ),
    responses={
        400: {"description": "Cancellation approval rejected"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Order not found"},
    },
)
async def approve_order_cancellation(
    order_id: int,
    request: OrderCancellationResolutionRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user),
) -> OrderCancellationResponse:
    """Approve one pending order cancellation request.

    Args:
        order_id: Order identifier from the route path.
        request: Empty request body used only to reject frontend-owned status
            or authorization claims.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        admin_user: Authenticated admin user authorizing the resolution.

    Returns:
        Customer-safe cancellation workflow response.

    Side effects:
        May stage a transition from `cancellation_requested` to `cancelled`
        and record an audit log in the same transaction. Payment confirmation
        and provider fulfillment history fields remain untouched.

    Raises:
        HTTPException: When the order is missing or not awaiting cancellation
            review.
    """
    return await _resolve_order_cancellation(
        order_id=order_id,
        request=request,
        db=db,
        admin_user=admin_user,
        approve=True,
    )


@router.post(
    "/{order_id}/cancellation-request/reject",
    response_model=OrderCancellationResponse,
    summary="Reject order cancellation request",
    description=(
        "Allows an authenticated admin to reject a pending customer "
        "cancellation request. Rejection restores the original paid status "
        "recorded in `cancellation_requested_from`, preserves payment and "
        "fulfillment history, and records an audit entry."
    ),
    responses={
        400: {"description": "Cancellation rejection rejected"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Order not found"},
    },
)
async def reject_order_cancellation(
    order_id: int,
    request: OrderCancellationResolutionRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user),
) -> OrderCancellationResponse:
    """Reject one pending order cancellation request.

    Args:
        order_id: Order identifier from the route path.
        request: Empty request body used only to reject frontend-owned status
            or authorization claims.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        admin_user: Authenticated admin user authorizing the resolution.

    Returns:
        Customer-safe cancellation workflow response.

    Side effects:
        May stage a transition from `cancellation_requested` back to the
        original paid status and record an audit log in the same transaction.
        Payment confirmation and provider fulfillment history fields remain
        untouched.

    Raises:
        HTTPException: When the order is missing, not awaiting cancellation
            review, or lacks a valid original paid status.
    """
    return await _resolve_order_cancellation(
        order_id=order_id,
        request=request,
        db=db,
        admin_user=admin_user,
        approve=False,
    )


async def _resolve_order_cancellation(
    *,
    order_id: int,
    request: OrderCancellationResolutionRequest,
    db: Session,
    admin_user: User,
    approve: bool,
) -> OrderCancellationResponse:
    """Resolve a pending cancellation request through the shared admin path.

    Args:
        order_id: Order identifier from the route path.
        request: Empty resolution body preserved for explicit validation.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        admin_user: Authenticated admin user authorizing the resolution.
        approve: Whether the admin outcome is approval instead of rejection.

    Returns:
        Customer-safe cancellation workflow response.

    Side effects:
        May stage the admin-approved or admin-rejected lifecycle transition and
        record a matching audit log inside the same transaction.

    Raises:
        HTTPException: When the order is missing, not awaiting review, or the
            stored prior state is invalid.
    """
    del request
    audit_log_repository = AuditLogRepository(db)
    service = OrderCancellationService(OrderRepository(db))

    try:
        result = (
            service.approve_cancellation(order_id)
            if approve
            else service.reject_cancellation(order_id)
        )
    except OrderCancellationRejected as exc:
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
            action=(
                ADMIN_CANCELLATION_APPROVAL_AUDIT_ACTION
                if approve
                else ADMIN_CANCELLATION_REJECTION_AUDIT_ACTION
            ),
            resource_type="order",
            resource_id=result.order.id,
            event_details={
                "from_status": result.from_status.value,
                "target_status": result.target_status.value,
                "order_status": result.order.status,
                "trigger": result.trigger.value,
                "cancellation_requested_from": (
                    result.cancellation_requested_from.value
                    if result.cancellation_requested_from is not None
                    else None
                ),
                "actor_type": "admin",
            },
        )
        db.commit()
        db.refresh(result.order)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "order_cancellation_resolution_audit_failed",
                "message": "Order cancellation resolution audit logging failed.",
            },
        ) from exc

    return OrderCancellationResponse(
        order_id=result.order.id,
        order_status=result.order.status,
        cancellation_requested_from=result.order.cancellation_requested_from,
        customer_safe_status=result.order.status,
    )
