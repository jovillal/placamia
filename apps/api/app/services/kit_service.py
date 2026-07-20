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

    def list_public_kits(self) -> list[Kit]:
        """List active catalog kits with at least one active required Product.

        Returns:
            Active kits that have at least one active Product in their required
            KitItem contents. Kits with zero active required contents are
            hidden from the public catalog.
        """
        return [kit for kit in self.list_kits() if self._is_public_kit(kit)]

    def get_public_kit(self, kit_id: int) -> Kit | None:
        """Return one publicly visible Kit by id.

        Args:
            kit_id: Kit identifier to retrieve.

        Returns:
            The active Kit when it has at least one active required Product,
            otherwise None.

        Side effects:
            Reads one Kit and its required contents through the repository.
        """
        kit = self.kit_repository.get_kit_by_id(kit_id)
        if kit is None or not self._is_public_kit(kit):
            return None
        return kit

    def list_public_kit_items(self, kit: Kit) -> list[KitItem]:
        """List public KitItems for one Kit.

        Args:
            kit: Kit whose bundle contents should be exposed.

        Returns:
            KitItems whose linked Product is active. Inactive Products are
            treated as unavailable catalog contents and are excluded.
        """
        return sorted(
            (item for item in kit.kit_items if item.product.is_active),
            key=lambda item: item.id if item.id is not None else 0,
        )

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

    def _is_public_kit(self, kit: Kit) -> bool:
        """Return whether one Kit may be exposed in the public catalog."""
        return kit.is_active and any(item.product.is_active for item in kit.kit_items)
