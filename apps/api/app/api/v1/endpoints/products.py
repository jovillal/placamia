from app.api.dependencies import get_provider_adapter
from app.core.database import get_db
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductRead
from app.services.product_eligibility_service import ProductEligibility
from app.services.product_service import ProductService
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter(prefix="/catalog/products", tags=["catalog"])


class ProductListResponse(BaseModel):
    """Response wrapper for public catalog product list endpoints."""

    data: list[ProductRead]


@router.get(
    "",
    response_model=ProductListResponse,
    summary="List catalog products",
    description=(
        "Returns active catalog products with backend-derived direct-checkout "
        "eligibility signals."
    ),
)
async def list_products(
    db: Session = Depends(get_db),
    provider_adapter=Depends(get_provider_adapter),
) -> dict[str, list[ProductRead]]:
    """Return active catalog products ordered by name.

    Args:
        db: SQLAlchemy session provided by FastAPI dependency injection.
        provider_adapter: Backend-owned provider adapter used to derive public
            availability and direct-checkout eligibility.

    Returns:
        A response payload containing public product records under the `data`
        key.

    Side effects:
        None.
    """
    product_repository = ProductRepository(db)
    product_service = ProductService(product_repository)
    products = product_service.list_products()

    return {
        "data": [
            _product_read_from_eligibility(
                product=product,
                eligibility=product_service.get_product_eligibility(
                    product=product,
                    provider_adapter=provider_adapter,
                ),
            )
            for product in products
        ]
    }


@router.get(
    "/{product_id}",
    response_model=ProductRead,
    summary="Get catalog product",
    description=(
        "Returns one active catalog product with backend-derived "
        "direct-checkout eligibility signals."
    ),
    responses={404: {"description": "Product not found"}},
)
async def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    provider_adapter=Depends(get_provider_adapter),
) -> ProductRead:
    """Return one active catalog product by id.

    Args:
        product_id: Product identifier from the request path.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        provider_adapter: Backend-owned provider adapter used to derive public
            availability and direct-checkout eligibility.

    Returns:
        The matching public product response.

    Side effects:
        None.

    Raises:
        HTTPException: When no active product exists for the requested id.
    """
    product_repository = ProductRepository(db)
    product_service = ProductService(product_repository)
    product = product_service.get_product(product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return _product_read_from_eligibility(
        product=product,
        eligibility=product_service.get_product_eligibility(
            product=product,
            provider_adapter=provider_adapter,
        ),
    )


def _product_read_from_eligibility(
    product,
    eligibility: ProductEligibility,
) -> ProductRead:
    """Build a public Product response with backend-derived eligibility fields."""
    return ProductRead(
        id=product.id,
        name=product.name,
        description=product.description,
        category_id=product.category_id,
        base_price=product.base_price,
        availability_state=eligibility.availability_state.value,
        direct_checkout_eligible=eligibility.direct_checkout_eligible,
        eligibility_reason=eligibility.eligibility_reason,
        production_lead_time_days=eligibility.production_lead_time_days,
        dispatch_lead_time_days=eligibility.dispatch_lead_time_days,
    )
