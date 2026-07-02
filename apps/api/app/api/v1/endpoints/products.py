from app.api.dependencies import get_provider_adapter
from app.core.database import get_db
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductRead
from app.services.product_eligibility_service import ProductEligibility
from app.services.product_service import ProductService
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter(prefix="/catalog/products", tags=["catalog"])

ALLOWED_PRODUCT_LIST_QUERY_PARAMS = frozenset({"category_id", "page", "page_size"})
MAX_PRODUCT_PAGE_SIZE = 50


class ProductListMeta(BaseModel):
    """Pagination metadata for public catalog product browsing responses."""

    page: int
    page_size: int
    total_items: int
    total_pages: int


class ProductListResponse(BaseModel):
    """Response wrapper for public catalog product list endpoints."""

    data: list[ProductRead]
    meta: ProductListMeta


@router.get(
    "",
    response_model=ProductListResponse,
    summary="List catalog products",
    description=(
        "Returns active catalog products with backend-derived direct-checkout "
        "eligibility signals. Supports category filtering and bounded "
        "pagination using category_id, page, and page_size only."
    ),
    responses={422: {"description": "Invalid or unsupported query parameter"}},
)
async def list_products(
    request: Request,
    category_id: int | None = Query(default=None, gt=0),
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=20, gt=0, le=MAX_PRODUCT_PAGE_SIZE),
    db: Session = Depends(get_db),
    provider_adapter=Depends(get_provider_adapter),
) -> ProductListResponse:
    """Return active catalog products ordered by name and id.

    Args:
        request: Incoming request used to reject unsupported query parameters.
        category_id: Optional positive category identifier filter.
        page: One-based page number. Defaults to 1.
        page_size: Positive page size up to 50. Defaults to 20.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        provider_adapter: Backend-owned provider adapter used to derive public
            availability and direct-checkout eligibility.

    Returns:
        A response payload containing public product records under `data` and
        pagination metadata under `meta`.

    Side effects:
        None.

    Raises:
        HTTPException: When unsupported query parameters are supplied.
    """
    _reject_unsupported_product_list_query_params(request)

    product_repository = ProductRepository(db)
    product_service = ProductService(product_repository)
    products, total_items = product_service.list_products_page(
        category_id=category_id,
        page=page,
        page_size=page_size,
    )

    return ProductListResponse(
        data=[
            _product_read_from_eligibility(
                product=product,
                eligibility=product_service.get_product_eligibility(
                    product=product,
                    provider_adapter=provider_adapter,
                ),
            )
            for product in products
        ],
        meta=ProductListMeta(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=_total_pages(total_items=total_items, page_size=page_size),
        ),
    )


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


def _reject_unsupported_product_list_query_params(request: Request) -> None:
    """Reject query parameters outside the documented public product contract."""
    unsupported_params = sorted(
        set(request.query_params.keys()) - ALLOWED_PRODUCT_LIST_QUERY_PARAMS
    )
    if unsupported_params:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "unsupported_query_parameter",
                "message": "Unsupported query parameter.",
                "unsupported_parameters": unsupported_params,
            },
        )


def _total_pages(*, total_items: int, page_size: int) -> int:
    """Return the number of available pages for a bounded product listing."""
    if total_items == 0:
        return 0
    return (total_items + page_size - 1) // page_size
