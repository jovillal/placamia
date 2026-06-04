from app.models.product import Product
from app.repositories.product_repository import ProductRepository
from app.domain.provider_adapter import ProviderAdapter
from app.services.catalog_eligibility_service import (
    CatalogEligibility,
    CatalogEligibilityService,
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

    def get_product(self, product_id: int) -> Product | None:
        """Get a single active catalog product by identifier.

        Args:
            product_id: Product identifier to look up.

        Returns:
            The matching active product model instance, or None when no active
            product exists.
        """
        return self.product_repository.get_active_product_by_id(product_id)

    def get_catalog_eligibility(
        self,
        product: Product,
        provider_adapter: ProviderAdapter,
    ) -> CatalogEligibility:
        """Return public catalog eligibility signals for one Product.

        Args:
            product: Product whose eligibility should be derived.
            provider_adapter: Adapter boundary used for backend-owned provider
                responses.

        Returns:
            Adapter-backed eligibility information for the Product.
        """
        eligibility_service = CatalogEligibilityService(provider_adapter)
        return eligibility_service.evaluate_product(product)
