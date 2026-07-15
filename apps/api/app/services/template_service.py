from app.models.template import Template
from app.repositories.template_repository import TemplateRepository


class TemplateService:
    """Business service for reusable signage templates.

    The service coordinates Template read use cases while keeping Template
    separate from future user-customized Design behavior.
    """

    def __init__(self, template_repository: TemplateRepository) -> None:
        """Store the repository used by template read use cases.

        Args:
            template_repository: Repository that reads Template records.
        """
        self.template_repository = template_repository

    def list_templates(self) -> list[Template]:
        """List active reusable base templates available for customization.

        Returns:
            Active templates returned by the repository, ordered by name and
            id.
        """
        return self.template_repository.get_active_templates()

    def get_template(self, template_id: int) -> Template | None:
        """Get a single active reusable base template by identifier.

        Args:
            template_id: Template identifier to look up.

        Returns:
            The matching active Template model instance, or None when no active
            template exists.
        """
        return self.template_repository.get_active_template_by_id(template_id)
