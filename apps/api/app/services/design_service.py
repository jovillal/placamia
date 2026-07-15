from app.models.design import Design
from app.repositories.design_repository import DesignRepository
from app.services.design_validation_service import DesignValidationService


class DesignService:
    """Business service for persisted Design records.

    The service coordinates validation, backend-derived ownership, persistence,
    and owner-scoped retrieval while keeping pricing, order creation, endpoint
    behavior, and editing flows out of this boundary.
    """

    def __init__(
        self,
        design_repository: DesignRepository,
        design_validation_service: DesignValidationService,
    ) -> None:
        """Store collaborators used by Design persistence use cases.

        Args:
            design_repository: Repository that persists and reads Design
                records.
            design_validation_service: Service that validates submitted
                customization against backend-owned TemplateField definitions.
        """
        self.design_repository = design_repository
        self.design_validation_service = design_validation_service

    def create_design(
        self,
        customer_id: int,
        template_id: int,
        customization_values: dict[str, object],
    ) -> Design:
        """Validate and persist one customer-owned immutable MVP Design.

        Args:
            customer_id: Backend-derived authenticated customer identifier.
            template_id: Identifier of the Template the Design is derived from.
            customization_values: Submitted customization data keyed by
                TemplateField field_name.

        Returns:
            The Design returned by the repository after persistence.

        Side effects:
            Persists one Design only after validation succeeds.

        Raises:
            DesignValidationError: When the Template or submitted customization
                violates the backend-owned Design contract.
        """
        accepted_values = self.design_validation_service.validate_customization(
            template_id=template_id,
            customization_values=customization_values,
        )
        return self.design_repository.create_design(
            customer_id=customer_id,
            template_id=template_id,
            customization_values=accepted_values,
        )

    def get_design_for_customer(
        self,
        design_id: int,
        customer_id: int,
    ) -> Design | None:
        """Get one persisted Design owned by an authenticated customer.

        Args:
            design_id: Design identifier to look up.
            customer_id: Backend-derived authenticated customer identifier.

        Returns:
            The matching owned Design, or None when no matching Design exists.
        """
        return self.design_repository.get_design_for_customer(
            design_id,
            customer_id,
        )
