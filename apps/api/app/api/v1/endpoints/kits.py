from app.core.database import get_db
from app.repositories.kit_repository import KitRepository
from app.schemas.kit import KitItemRead, KitRead
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
    description="Returns active catalog kits with active product references.",
)
async def list_kits(
    db: Session = Depends(get_db),
) -> dict[str, list[KitRead]]:
    """Return active catalog kits ordered by name.

    Args:
        db: SQLAlchemy session provided by FastAPI dependency injection.

    Returns:
        A response payload containing public Kit records under the `data` key.

    Side effects:
        None.
    """
    kit_repository = KitRepository(db)
    kit_service = KitService(kit_repository)
    kits = kit_service.list_kits()

    return {
        "data": [
            KitRead(
                id=kit.id,
                name=kit.name,
                description=kit.description,
                items=[
                    KitItemRead.model_validate(item)
                    for item in kit_service.list_public_kit_items(kit)
                ],
            )
            for kit in kits
        ]
    }
