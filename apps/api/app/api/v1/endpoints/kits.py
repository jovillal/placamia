from app.api.dependencies import get_provider_adapter
from app.core.database import get_db
from app.repositories.kit_repository import KitRepository
from app.schemas.kit import KitItemRead, KitRead
from app.services.kit_eligibility_service import KitEligibility
from app.services.kit_service import KitService
from fastapi import APIRouter, Depends
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
