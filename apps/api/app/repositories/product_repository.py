from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product


class ProductRepository:
    """Data access layer for catalog products.

    The repository receives a SQLAlchemy session and performs product queries
    without applying business rules or pricing calculations.
    """

    def __init__(self, db: Session) -> None:
        """Store the database session used by product queries.

        Args:
            db: SQLAlchemy session bound to the current request or test.
        """
        self.db = db

    def get_products(self) -> list[Product]:
        """Return all products ordered by name.

        Returns:
            A list of product model instances sorted alphabetically.
        """
        result = self.db.execute(select(Product).order_by(Product.name))
        return list(result.scalars().all())

    def get_product_by_id(self, product_id: int) -> Product | None:
        """Return one product by primary key.

        Args:
            product_id: Product identifier to look up.

        Returns:
            The matching product model instance, or None when no product exists.
        """
        return self.db.get(Product, product_id)
