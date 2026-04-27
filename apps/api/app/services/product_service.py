from app.models.product import Product
from app.repositories.product_repository import ProductRepository


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
        """List catalog products available to the application.

        Returns:
            Products returned by the repository, currently ordered by name.
        """
        return self.product_repository.get_products()

    def get_product(self, product_id: int) -> Product | None:
        """Get a single catalog product by identifier.

        Args:
            product_id: Product identifier to look up.

        Returns:
            The matching product model instance, or None when no product exists.
        """
        return self.product_repository.get_product_by_id(product_id)
