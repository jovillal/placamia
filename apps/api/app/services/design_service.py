from app.models.design import Design
from app.repositories.design_repository import DesignRepository
from app.services.design_validation_service import DesignValidationService
from sqlalchemy.orm import Session


class DesignService:
    """Business service for persisted Design records.

    The service coordinates validation, backend-derived ownership, persistence,
    the creation transaction, and owner-scoped retrieval while keeping pricing,
    order creation, endpoint behavior, and editing flows out of this boundary.
    """

    def __init__(
        self,
        design_repository: DesignRepository,
        design_validation_service: DesignValidationService,
        db: Session,
    ) -> None:
        """Store collaborators used by Design persistence use cases.

        Args:
            design_repository: Repository that persists and reads Design
                records.
            design_validation_service: Service that validates submitted
                customization against backend-owned TemplateField definitions.
            db: Request-scoped database session that owns the creation
                transaction boundary.
        """
        self.design_repository = design_repository
        self.design_validation_service = design_validation_service
        self.db = db

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
            Stages and commits one Design only after validation succeeds. Rolls
            back the transaction if staging or commit fails.

        Raises:
            DesignValidationError: When the Template or submitted customization
                violates the backend-owned Design contract.
            Exception: Re-raises persistence or commit failures after rollback.
        """
        accepted_values = self.design_validation_service.validate_customization(
            template_id=template_id,
            customization_values=customization_values,
        )
        try:
            design = self.design_repository.create_design(
                customer_id=customer_id,
                template_id=template_id,
                customization_values=accepted_values,
            )
            self.db.commit()
            return design
        except Exception:
            self.db.rollback()
            raise

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
