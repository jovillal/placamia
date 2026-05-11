from app.models.design import Design
from app.repositories.design_repository import DesignRepository


class DesignService:
    """Business service for persisted Design records.

    The service coordinates persistence and retrieval of already-validated
    Design customization data while keeping validation, pricing, order
    creation, endpoint behavior, and editing flows out of this issue's scope.
    """

    def __init__(self, design_repository: DesignRepository) -> None:
        """Store the repository used by Design persistence use cases.

        Args:
            design_repository: Repository that persists and reads Design
                records.
        """
        self.design_repository = design_repository

    def create_design(
        self,
        template_id: int,
        customization_values: dict[str, object],
    ) -> Design:
        """Persist one already-validated MVP Design.

        Args:
            template_id: Identifier of the Template the Design is derived from.
            customization_values: Backend-validated customization data keyed by
                TemplateField field_name.

        Returns:
            The Design returned by the repository after persistence.

        Side effects:
            Delegates record creation to the Design repository.
        """
        return self.design_repository.create_design(
            template_id=template_id,
            customization_values=customization_values,
        )

    def get_design(self, design_id: int) -> Design | None:
        """Get a single persisted Design by identifier.

        Args:
            design_id: Design identifier to look up.

        Returns:
            The matching Design model instance, or None when no Design exists.
        """
        return self.design_repository.get_design_by_id(design_id)
