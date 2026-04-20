from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


class CategoryRepository:
    """Data access layer for catalog categories.

    The repository receives a SQLAlchemy session and performs category queries
    without applying business rules.
    """

    def __init__(self, db: Session) -> None:
        """Store the database session used by category queries.

        Args:
            db: SQLAlchemy session bound to the current request or test.
        """
        self.db = db

    def list_categories(self) -> list[Category]:
        """Return all categories ordered by name.

        Returns:
            A list of category model instances sorted alphabetically.
        """
        result = self.db.execute(select(Category).order_by(Category.name))
        return list(result.scalars().all())
