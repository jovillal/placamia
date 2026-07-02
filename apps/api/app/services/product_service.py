from app.domain.provider_adapter import ProviderAdapter
from app.models.product import Product
from app.repositories.product_repository import ProductRepository
from app.services.product_eligibility_service import (
    ProductEligibility,
    ProductEligibilityService,
)


class ProductService:
    """Business service for catalog products.

    The service coordinates product use cases while keeping persistence details
    inside the repository layer.
    """

    def __init__(self, product_repository: ProductRepository) -> None:
        """Store the repository used by product use cases.

        Args:
            product_repository: Repository that reads product records.
        """
        self.product_repository = product_repository

    def list_products(self) -> list[Product]:
        """List active catalog products available to customers.

        Returns:
            Active products returned by the repository, currently ordered by
            name.
        """
        return self.product_repository.get_active_products()

    def list_products_page(
        self,
        *,
        category_id: int | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Product], int]:
        """List one active catalog product page for public browsing.

        Args:
            category_id: Optional category identifier used to narrow active
                products.
            page: One-based page number.
            page_size: Maximum number of products to include in the page.

        Returns:
            A tuple containing the active Product page and the total number of
            active Products matching the filter before pagination.
        """
        offset = (page - 1) * page_size
        return (
            self.product_repository.get_active_products_page(
                category_id=category_id,
                offset=offset,
                limit=page_size,
            ),
            self.product_repository.count_active_products(category_id=category_id),
        )

    def get_product(self, product_id: int) -> Product | None:
        """Get a single active catalog product by identifier.

        Args:
            product_id: Product identifier to look up.

        Returns:
            The matching active product model instance, or None when no active
            product exists.
        """
        return self.product_repository.get_active_product_by_id(product_id)

    def get_product_eligibility(
        self,
        product: Product,
        provider_adapter: ProviderAdapter,
    ) -> ProductEligibility:
        """Return backend-derived public eligibility for one Product.

        Args:
            product: Product whose public direct-checkout signals should be
                derived.
            provider_adapter: Backend-owned provider adapter boundary.

        Returns:
            Public eligibility fields derived from backend state and adapter
            responses.
        """
        eligibility_service = ProductEligibilityService(provider_adapter)
        return eligibility_service.evaluate_product(product)
