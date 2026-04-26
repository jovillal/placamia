from app.models.category import Category
from app.repositories.category_repository import CategoryRepository


class CategoryService:
    """Business service for catalog categories.

    The service coordinates category use cases and keeps route handlers thin.
    """

    def __init__(self, category_repository: CategoryRepository) -> None:
        """Store the repository used by category use cases.

        Args:
            category_repository: Repository that reads category records.
        """
        self.category_repository = category_repository

    def list_categories(self) -> list[Category]:
        """List catalog categories available to customers.

        Returns:
            Categories returned by the repository, currently ordered by name.
        """
        return self.category_repository.list_categories()
