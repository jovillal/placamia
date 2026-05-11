from app.models.template import Template
from sqlalchemy import select
from sqlalchemy.orm import Session


class TemplateRepository:
    """Data access layer for reusable signage templates.

    The repository receives a SQLAlchemy session and performs read queries for
    Template records without creating Designs or storing customization values.
    """

    def __init__(self, db: Session) -> None:
        """Store the database session used by template queries.

        Args:
            db: SQLAlchemy session bound to the current request or test.
        """
        self.db = db

    def get_active_templates(self) -> list[Template]:
        """Return active reusable base templates ordered by name.

        Returns:
            A list of active Template model instances sorted alphabetically.
        """
        result = self.db.execute(
            select(Template).where(Template.is_active.is_(True)).order_by(Template.name)
        )
        return list(result.scalars().all())

    def get_active_template_by_id(self, template_id: int) -> Template | None:
        """Return one active reusable base template by primary key.

        Args:
            template_id: Template identifier to look up.

        Returns:
            The matching active Template model instance, or None when no active
            template exists.
        """
        result = self.db.execute(
            select(Template).where(
                Template.id == template_id,
                Template.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    def get_template_by_id(self, template_id: int) -> Template | None:
        """Return one reusable base template by primary key regardless of state.

        Args:
            template_id: Template identifier to look up.

        Returns:
            The matching Template model instance, or None when no template
            exists.
        """
        result = self.db.execute(select(Template).where(Template.id == template_id))
        return result.scalar_one_or_none()
