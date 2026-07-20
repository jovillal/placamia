from app.api.dependencies import get_provider_adapter
from app.core.database import get_db
from app.repositories.kit_repository import KitRepository
from app.schemas.kit import KitItemRead, KitRead
from app.services.kit_eligibility_service import KitEligibility
from app.services.kit_service import KitService
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter(prefix="/catalog/kits", tags=["catalog"])


class KitListResponse(BaseModel):
    """Response wrapper for public catalog kit list endpoints."""

    data: list[KitRead]


@router.get(
    "",
    response_model=KitListResponse,
    summary="List catalog kits",
    description=(
        "Returns active catalog kits with customer-safe active product "
        "summaries and backend-derived direct-checkout eligibility signals."
    ),
)
async def list_kits(
    db: Session = Depends(get_db),
    provider_adapter=Depends(get_provider_adapter),
) -> KitListResponse:
    """Return active catalog kits ordered by name.

    Args:
        db: SQLAlchemy session provided by FastAPI dependency injection.
        provider_adapter: Backend-owned provider adapter used to derive public
            availability and direct-checkout eligibility.

    Returns:
        A response payload containing public Kit records under the `data` key.

    Side effects:
        None.
    """
    kit_repository = KitRepository(db)
    kit_service = KitService(kit_repository)
    kits = kit_service.list_public_kits()

    return KitListResponse(
        data=[
            _kit_read_from_eligibility(
                kit=kit,
                items=kit_service.list_public_kit_items(kit),
                eligibility=kit_service.get_kit_eligibility(
                    kit=kit,
                    provider_adapter=provider_adapter,
                ),
            )
            for kit in kits
        ]
    )


@router.get(
    "/{kit_id}",
    response_model=KitRead,
    summary="Get catalog kit",
    description=(
        "Returns one visible active catalog Kit with customer-safe active "
        "Product summaries and backend-derived direct-checkout eligibility "
        "signals. This endpoint accepts no query parameters."
    ),
    responses={
        404: {"description": "Kit not found"},
        422: {"description": "Unsupported query parameter"},
    },
)
async def get_kit(
    kit_id: int,
    request: Request,
    db: Session = Depends(get_db),
    provider_adapter=Depends(get_provider_adapter),
) -> KitRead:
    """Return one publicly visible catalog Kit by id.

    Args:
        kit_id: Kit identifier from the request path.
        request: Incoming request used to reject every query parameter.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        provider_adapter: Backend-owned provider adapter used to derive public
            availability and direct-checkout eligibility.

    Returns:
        The matching public Kit response.

    Side effects:
        None.

    Raises:
        HTTPException: When query parameters are supplied or the Kit is not
            publicly visible.
    """
    _reject_kit_detail_query_params(request)

    kit_service = KitService(KitRepository(db))
    kit = kit_service.get_public_kit(kit_id)
    if kit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kit not found",
        )

    return _kit_read_from_eligibility(
        kit=kit,
        items=kit_service.list_public_kit_items(kit),
        eligibility=kit_service.get_kit_eligibility(
            kit=kit,
            provider_adapter=provider_adapter,
        ),
    )


def _kit_read_from_eligibility(
    kit,
    items,
    eligibility: KitEligibility,
) -> KitRead:
    """Build a public Kit response with backend-derived eligibility fields."""
    return KitRead(
        id=kit.id,
        name=kit.name,
        description=kit.description,
        items=[_kit_item_read(item) for item in items],
        availability_state=eligibility.availability_state.value,
        direct_checkout_eligible=eligibility.direct_checkout_eligible,
        eligibility_reason=eligibility.eligibility_reason,
        production_lead_time_days=eligibility.production_lead_time_days,
        dispatch_lead_time_days=eligibility.dispatch_lead_time_days,
    )


def _kit_item_read(item) -> KitItemRead:
    """Build a customer-safe public Product summary for one KitItem."""
    return KitItemRead(
        product_id=item.product_id,
        name=item.product.name,
        description=item.product.description,
        category_id=item.product.category_id,
        quantity=item.quantity,
    )


def _reject_kit_detail_query_params(request: Request) -> None:
    """Reject every query parameter for the public Kit detail contract."""
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
