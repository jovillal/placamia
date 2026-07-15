from app.models.design import Design
from sqlalchemy import select
from sqlalchemy.orm import Session


class DesignRepository:
    """Data access layer for persisted Design records.

    The repository receives a SQLAlchemy session and persists or retrieves
    already-validated Design customization values. Validation, pricing, order
    creation, endpoint behavior, and editing flows belong outside this layer.
    """

    def __init__(self, db: Session) -> None:
        """Store the database session used by Design persistence queries.

        Args:
            db: SQLAlchemy session bound to the current request or test.
        """
        self.db = db

    def create_design(
        self,
        customer_id: int,
        template_id: int,
        customization_values: dict[str, object],
    ) -> Design:
        """Persist one immutable MVP Design for a Template.

        Args:
            customer_id: Backend-derived authenticated customer identifier.
            template_id: Identifier of the Template the Design is derived from.
            customization_values: Backend-validated customization data keyed by
                TemplateField field_name.

        Returns:
            The persisted Design model instance with database-generated fields
            populated.

        Side effects:
            Adds and commits a Design record using the current database session.
        """
        design = Design(
            customer_id=customer_id,
            template_id=template_id,
            customization_values=customization_values,
        )
        self.db.add(design)
        self.db.commit()
        self.db.refresh(design)
        return design

    def get_design_for_customer(
        self,
        design_id: int,
        customer_id: int,
    ) -> Design | None:
        """Return one persisted Design owned by an authenticated customer.

        Args:
            design_id: Design identifier to look up.
            customer_id: Backend-derived authenticated customer identifier.

        Returns:
            The matching customer-owned Design, or None when no matching owned
            Design exists.
        """
        result = self.db.execute(
            select(Design).where(
                Design.id == design_id,
                Design.customer_id == customer_id,
            )
        )
        return result.scalar_one_or_none()
