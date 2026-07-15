from app.models.template import Template
from app.models.template_field import TemplateField
from sqlalchemy import select
from sqlalchemy.orm import Session


class TemplateFieldRepository:
    """Data access layer for TemplateField definitions.

    The repository receives a SQLAlchemy session and reads active field
    definitions for active Templates without creating Designs or storing user
    customization values.
    """

    def __init__(self, db: Session) -> None:
        """Store the database session used by TemplateField queries.

        Args:
            db: SQLAlchemy session bound to the current request or test.
        """
        self.db = db

    def get_active_fields_for_template(self, template_id: int) -> list[TemplateField]:
        """Return active fields for one active Template ordered for display.

        Args:
            template_id: Template identifier whose field definitions should be
                retrieved.

        Returns:
            Active TemplateField model instances ordered by display_order and
            id. An empty list is returned when the Template is missing or
            inactive.
        """
        result = self.db.execute(
            select(TemplateField)
            .join(Template)
            .where(
                Template.id == template_id,
                Template.is_active.is_(True),
                TemplateField.is_active.is_(True),
            )
            .order_by(TemplateField.display_order, TemplateField.id)
        )
        return list(result.scalars().all())
