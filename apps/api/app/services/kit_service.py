from app.domain.provider_adapter import ProviderAdapter
from app.models.kit import Kit
from app.models.kit_item import KitItem
from app.repositories.kit_repository import KitRepository
from app.services.kit_eligibility_service import (
    KitEligibility,
    KitEligibilityService,
)


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

    def list_public_kit_items(self, kit: Kit) -> list[KitItem]:
        """List public KitItems for one Kit.

        Args:
            kit: Kit whose bundle contents should be exposed.

        Returns:
            KitItems whose linked Product is active. Inactive Products are
            treated as unavailable catalog contents and are excluded.
        """
        return [item for item in kit.kit_items if item.product.is_active]

    def get_kit_eligibility(
        self,
        kit: Kit,
        provider_adapter: ProviderAdapter,
    ) -> KitEligibility:
        """Return backend-derived public eligibility for one Kit.

        Args:
            kit: Kit whose public direct-checkout signals should be derived.
            provider_adapter: Backend-owned provider adapter boundary.

        Returns:
            Public eligibility fields derived from backend-owned kit contents
            and adapter responses.
        """
        eligibility_service = KitEligibilityService(provider_adapter)
        return eligibility_service.evaluate_kit(kit)
