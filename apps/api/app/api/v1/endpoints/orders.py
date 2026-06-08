from app.api.dependencies import get_current_user, get_provider_adapter
from app.core.database import get_db
from app.models.user import User
from app.repositories.kit_repository import KitRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.order import OrderCreateRequest, OrderRead
from app.services.checkout_service import CheckoutEligibilityService
from app.services.order_creation_service import OrderCreationRejected
from app.services.order_creation_service import OrderCreationService
from app.services.pricing_service import PathAPricingService
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/orders", tags=["orders"])


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
