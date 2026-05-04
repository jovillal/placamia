from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductRead
from app.services.product_service import ProductService

router = APIRouter(prefix="/catalog/products", tags=["catalog"])


class ProductListResponse(BaseModel):
    """Response wrapper for public catalog product list endpoints."""

    data: list[ProductRead]


@router.get(
    "",
    response_model=ProductListResponse,
    summary="List catalog products",
    description="Returns active catalog products that customers can browse.",
)
async def list_products(
    db: Session = Depends(get_db),
) -> dict[str, list[ProductRead]]:
    """Return active catalog products ordered by name.

    Args:
        db: SQLAlchemy session provided by FastAPI dependency injection.

    Returns:
        A response payload containing public product records under the `data`
        key.

    Side effects:
        None.
    """
    product_repository = ProductRepository(db)
    product_service = ProductService(product_repository)
    products = product_service.list_products()

    return {"data": [ProductRead.model_validate(product) for product in products]}
