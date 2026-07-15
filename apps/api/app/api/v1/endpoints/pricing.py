from app.api.dependencies import get_optional_current_user, get_provider_adapter
from app.core.database import get_db
from app.models.user import User
from app.repositories.design_repository import DesignRepository
from app.repositories.kit_repository import KitRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.template_field_repository import TemplateFieldRepository
from app.repositories.template_repository import TemplateRepository
from app.schemas.pricing import (
    DesignPricingQuoteResponse,
    KitPricingLineResponse,
    KitPricingQuoteResponse,
    PricingQuoteRequest,
    PricingQuoteResponse,
    ProductPricingQuoteResponse,
)
from app.services.design_validation_service import DesignValidationService
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
        "direct-checkout Products, fixed-content Kits, and authenticated "
        "customer-owned persisted Designs."
    ),
    responses={
        400: {"description": "Pricing request rejected with a stable detail code"},
        401: {"description": "Authentication required for Design pricing"},
        404: {"description": "Pricing item not found or not owned"},
    },
    openapi_extra={"security": [{}]},
)
async def preview_pricing_quote(
    request: PricingQuoteRequest,
    db: Session = Depends(get_db),
    provider_adapter=Depends(get_provider_adapter),
    current_user: User | None = Depends(get_optional_current_user),
) -> PricingQuoteResponse:
    """Return a backend-owned Product, Kit, or persisted Design preview.

    Args:
        request: Validated pricing quote request body.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        provider_adapter: Backend-owned provider adapter used for eligibility
            and provider cost/capability checks.
        current_user: Optional authenticated user required for Design pricing.

    Returns:
        Temporary Product, Kit, or Design pricing preview.

    Side effects:
        None. The endpoint does not create orders, payments, designs, checkout
        records, or provider handoffs.

    Raises:
        HTTPException: When the item is missing or pricing rejects the request.
    """
    pricing_request = _pricing_request_from_api_request(request, db, current_user)
    pricing_service = PathAPricingService(
        provider_adapter,
        design_validation_service=DesignValidationService(
            TemplateRepository(db),
            TemplateFieldRepository(db),
        ),
    )

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

    if preview.item_type is PricingItemType.DESIGN:
        return DesignPricingQuoteResponse(
            item_type=PricingItemType.DESIGN,
            item_id=preview.item_id,
            quantity=preview.quantity,
            currency=preview.currency,
            customer_unit_price=preview.customer_unit_price,
            customer_subtotal=preview.customer_subtotal,
            preview_total=preview.customer_total,
            pricing_rule=preview.pricing_rule,
            provider_quote_reference=preview.provider_quote_reference,
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
    current_user: User | None,
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
    elif request.item_type is PricingItemType.DESIGN:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        design = DesignRepository(db).get_design_for_customer_pricing(
            request.item_id,
            current_user.id,
        )
        if design is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "design_not_found",
                    "message": "Design not found.",
                },
            )
        item = design
    else:
        item = object()

    return PathAPricingRequest(
        item_type=request.item_type,
        item=item,
        quantity=request.quantity,
        options=getattr(request, "options", {}),
        frontend_claims=request.frontend_claims(),
    )
