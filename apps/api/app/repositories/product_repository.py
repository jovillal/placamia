from app.models.product import Product
from sqlalchemy import func, select
from sqlalchemy.orm import Session


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

    def get_active_products(self) -> list[Product]:
        """Return active products ordered by name.

        Returns:
            A list of active product model instances sorted alphabetically.
        """
        result = self.db.execute(
            select(Product)
            .where(Product.is_active.is_(True))
            .order_by(Product.name, Product.id)
        )
        return list(result.scalars().all())

    def get_active_products_page(
        self,
        *,
        category_id: int | None,
        offset: int,
        limit: int,
    ) -> list[Product]:
        """Return one page of active products ordered by name and id.

        Args:
            category_id: Optional category identifier used to narrow active
                products.
            offset: Number of matching active products to skip.
            limit: Maximum number of matching active products to return.

        Returns:
            A stable page of active product model instances.
        """
        filters = [Product.is_active.is_(True)]
        if category_id is not None:
            filters.append(Product.category_id == category_id)

        result = self.db.execute(
            select(Product)
            .where(*filters)
            .order_by(Product.name.asc(), Product.id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    def count_active_products(self, *, category_id: int | None) -> int:
        """Count active products, optionally narrowed by category.

        Args:
            category_id: Optional category identifier used to narrow active
                products.

        Returns:
            Number of active products visible through the public catalog.
        """
        filters = [Product.is_active.is_(True)]
        if category_id is not None:
            filters.append(Product.category_id == category_id)

        return self.db.scalar(select(func.count()).select_from(Product).where(*filters))

    def get_product_by_id(self, product_id: int) -> Product | None:
        """Return one product by primary key.

        Args:
            product_id: Product identifier to look up.

        Returns:
            The matching product model instance, or None when no product exists.
        """
        return self.db.get(Product, product_id)

    def get_active_product_by_id(self, product_id: int) -> Product | None:
        """Return one active product by primary key.

        Args:
            product_id: Product identifier to look up.

        Returns:
            The matching active product model instance, or None when no active
            product exists.
        """
        result = self.db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()
