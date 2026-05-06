from app.models.kit import Kit
from app.repositories.kit_repository import KitRepository


class KitService:
    """Business service for curated catalog kits.

    The service coordinates read-only Kit use cases while keeping persistence
    details in the repository layer and leaving pricing, discounts, checkout,
    and admin behavior to later scopes.
    """

    def __init__(self, kit_repository: KitRepository) -> None:
        """Store the repository used by Kit read use cases.

        Args:
            kit_repository: Repository that reads Kit records.
        """
        self.kit_repository = kit_repository

    def list_kits(self) -> list[Kit]:
        """List active catalog kits available to customers.

        Returns:
            Active kits returned by the repository, currently ordered by name.
        """
        return self.kit_repository.get_active_kits()
