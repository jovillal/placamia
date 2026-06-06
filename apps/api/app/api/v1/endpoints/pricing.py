from app.api.dependencies import get_provider_adapter
from app.core.database import get_db
from app.repositories.product_repository import ProductRepository
from app.schemas.pricing import PricingQuoteRequest, PricingQuoteResponse
from app.services.pricing_service import (
    PathAPricingRequest,
    PathAPricingService,
    PricingItemType,
    PricingRejected,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.post(
    "/quotes",
    response_model=PricingQuoteResponse,
    summary="Preview Path A pricing",
    description=(
        "Returns a backend-calculated temporary pricing preview for eligible "
        "direct-checkout products. Kit and design pricing remain deferred."
    ),
    responses={
        400: {"description": "Pricing request rejected"},
        404: {"description": "Catalog item not found"},
    },
)
async def preview_pricing_quote(
    request: PricingQuoteRequest,
    db: Session = Depends(get_db),
    provider_adapter=Depends(get_provider_adapter),
) -> PricingQuoteResponse:
    """Return a backend-owned pricing preview for a Path A product request.

    Args:
        request: Validated pricing quote request body.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        provider_adapter: Backend-owned provider adapter used for eligibility
            and provider cost/capability checks.

    Returns:
        Temporary product pricing preview from the pricing service.

    Side effects:
        None. The endpoint does not create orders, payments, designs, checkout
        records, or provider handoffs.

    Raises:
        HTTPException: When the item is missing or pricing rejects the request.
    """
    pricing_request = _pricing_request_from_api_request(request, db)
    pricing_service = PathAPricingService(provider_adapter)

    try:
        preview = pricing_service.preview_price(pricing_request)
    except PricingRejected as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return PricingQuoteResponse(
        item_type=preview.item_type,
        item_id=preview.item_id,
        quantity=preview.quantity,
        currency=preview.currency,
        customer_unit_price=preview.customer_unit_price,
        customer_subtotal=preview.customer_subtotal,
        preview_total=preview.customer_total,
        pricing_rule=preview.pricing_rule,
        provider_quote_reference=preview.provider_quote_reference,
    )


def _pricing_request_from_api_request(
    request: PricingQuoteRequest,
    db: Session,
) -> PathAPricingRequest:
    """Build a backend-owned service request from a public API request."""
    if request.item_type is PricingItemType.PRODUCT:
        product = ProductRepository(db).get_product_by_id(request.item_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "product_not_found", "message": "Product not found."},
            )
        item = product
    else:
        item = object()

    return PathAPricingRequest(
        item_type=request.item_type,
        item=item,
        quantity=request.quantity,
        options=request.options,
        frontend_claims=request.frontend_claims(),
    )
