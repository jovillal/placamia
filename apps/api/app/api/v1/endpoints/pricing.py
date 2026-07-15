from app.api.dependencies import get_provider_adapter
from app.core.database import get_db
from app.repositories.kit_repository import KitRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.pricing import (
    KitPricingLineResponse,
    KitPricingQuoteResponse,
    PricingQuoteRequest,
    PricingQuoteResponse,
    ProductPricingQuoteResponse,
)
from app.services.pricing_service import (
    PathAKitPricingPreview,
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
        "direct-checkout Products and fixed-content Kits. Design pricing "
        "remains deferred."
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
    """Return a backend-owned pricing preview for a Product or fixed Kit.

    Args:
        request: Validated pricing quote request body.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        provider_adapter: Backend-owned provider adapter used for eligibility
            and provider cost/capability checks.

    Returns:
        Temporary Product or Kit pricing preview from the pricing service.

    Side effects:
        None. The endpoint does not create orders, payments, designs, checkout
        records, or provider handoffs.

    Raises:
        HTTPException: When the item is missing or pricing rejects the request.
    """
    pricing_request = _pricing_request_from_api_request(request, db)
    pricing_service = PathAPricingService(provider_adapter)

    try:
        preview = pricing_service.preview_quote(pricing_request)
    except PricingRejected as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    if isinstance(preview, PathAKitPricingPreview):
        return KitPricingQuoteResponse(
            item_type=PricingItemType.KIT,
            item_id=preview.item_id,
            quantity=preview.quantity,
            currency=preview.currency,
            customer_unit_price=preview.customer_unit_price,
            customer_subtotal=preview.customer_subtotal,
            preview_total=preview.customer_total,
            pricing_rule=preview.pricing_rule,
            provider_quote_reference=preview.provider_quote_reference,
            lines=[
                KitPricingLineResponse(
                    product_id=line.product_id,
                    product_name=line.product_name,
                    quantity_per_kit=line.quantity_per_kit,
                    total_quantity=line.total_quantity,
                    customer_unit_price=line.customer_unit_price,
                    customer_subtotal=line.customer_subtotal,
                )
                for line in preview.lines
            ],
        )

    return ProductPricingQuoteResponse(
        item_type=PricingItemType.PRODUCT,
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
    elif request.item_type is PricingItemType.KIT:
        kit = KitRepository(db).get_kit_by_id(request.item_id)
        if kit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "kit_not_found", "message": "Kit not found."},
            )
        item = kit
    else:
        item = object()

    return PathAPricingRequest(
        item_type=request.item_type,
        item=item,
        quantity=request.quantity,
        options=request.options,
        frontend_claims=request.frontend_claims(),
    )
