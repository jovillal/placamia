from app.core.database import get_db
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryRead
from app.services.category_service import CategoryService
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter(prefix="/catalog/categories", tags=["catalog"])


class CategoryListResponse(BaseModel):
    """Response wrapper for category list endpoints."""

    data: list[CategoryRead]


@router.get(
    "",
    response_model=CategoryListResponse,
    summary="List catalog categories",
    description="Returns the catalog categories that group sellable signage products.",
)
async def list_categories(
    db: Session = Depends(get_db),
) -> dict[str, list[CategoryRead]]:
    """Return catalog categories ordered by name.

    Args:
        db: SQLAlchemy session provided by FastAPI dependency injection.

    Returns:
        A response payload containing category records under the `data` key.
    """
    category_repository = CategoryRepository(db)
    category_service = CategoryService(category_repository)
    categories = category_service.list_categories()

    return {"data": [CategoryRead.model_validate(category) for category in categories]}
