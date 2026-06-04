from app.models.template_field import TemplateField
from app.repositories.template_field_repository import TemplateFieldRepository


class TemplateFieldService:
    """Business service for TemplateField definition reads.

    The service coordinates retrieval of allowed Template customization inputs
    while keeping future Design persistence and validation behavior out of this
    layer.
    """

    def __init__(self, template_field_repository: TemplateFieldRepository) -> None:
        """Store the repository used by TemplateField read use cases.

        Args:
            template_field_repository: Repository that reads TemplateField
                records.
        """
        self.template_field_repository = template_field_repository

    def list_fields_for_template(self, template_id: int) -> list[TemplateField]:
        """List active customization fields for one active Template.

        Args:
            template_id: Template identifier whose fields should be returned.

        Returns:
            Active TemplateFields returned by the repository, currently ordered
            by display_order.
        """
        return self.template_field_repository.get_active_fields_for_template(template_id)
