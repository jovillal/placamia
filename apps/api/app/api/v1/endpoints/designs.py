from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repositories.design_repository import DesignRepository
from app.repositories.template_field_repository import TemplateFieldRepository
from app.repositories.template_repository import TemplateRepository
from app.schemas.design import DesignCreateRequest, DesignRead
from app.services.design_service import DesignService
from app.services.design_validation_service import (
    DesignValidationError,
    DesignValidationService,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/designs", tags=["designs"])

CONFIGURATION_ERROR_CODES = {
    "ambiguous_template_field",
    "invalid_allowed_values",
    "unsupported_field_type",
}
TEMPLATE_NOT_FOUND_CODES = {
    "template_inactive",
    "template_not_found",
}


def build_design_service(db: Session) -> DesignService:
    """Build the Design application service for one request session.

    Args:
        db: SQLAlchemy session used for validation and persistence.

    Returns:
        Design service sharing the request-scoped database session.

    Side effects:
        None.
    """
    return DesignService(
        DesignRepository(db),
        DesignValidationService(
            TemplateRepository(db),
            TemplateFieldRepository(db),
        ),
        db,
    )


@router.post(
    "",
    response_model=DesignRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Design",
    description=(
        "Validates Template customization against backend-owned active fields "
        "and persists one immutable Design owned by the authenticated customer."
    ),
    responses={
        400: {"description": "Customization rejected"},
        401: {"description": "Authentication required"},
        404: {"description": "Template not found"},
        409: {"description": "Design configuration unavailable"},
    },
)
async def create_design(
    request: DesignCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DesignRead:
    """Create one validated immutable Design for the authenticated customer.

    Args:
        request: Strict Template identifier and customization values.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        current_user: Authenticated owner resolved from the bearer token.

    Returns:
        Customer-safe persisted Design representation.

    Side effects:
        Persists one Design after all backend validation succeeds.

    Raises:
        HTTPException: When Template lookup, customization validation, or
            backend TemplateField configuration rejects creation.
    """
    try:
        design = build_design_service(db).create_design(
            customer_id=current_user.id,
            template_id=request.template_id,
            customization_values=request.customization_values,
        )
    except DesignValidationError as exc:
        if exc.code in TEMPLATE_NOT_FOUND_CODES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            ) from exc
        if exc.code in CONFIGURATION_ERROR_CODES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "design_configuration_unavailable",
                    "message": "Design configuration is unavailable.",
                },
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return DesignRead.model_validate(design)


@router.get(
    "/{design_id}",
    response_model=DesignRead,
    summary="Get Design",
    description=(
        "Returns one immutable Design only when it belongs to the authenticated "
        "customer. Unknown and cross-customer identifiers are concealed alike."
    ),
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Design not found"},
    },
)
async def get_design(
    design_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DesignRead:
    """Return one customer-safe Design owned by the authenticated customer.

    Args:
        design_id: Design identifier from the request path.
        db: SQLAlchemy session provided by FastAPI dependency injection.
        current_user: Authenticated owner resolved from the bearer token.

    Returns:
        Customer-safe persisted Design representation.

    Side effects:
        None.

    Raises:
        HTTPException: When the Design is missing or belongs to another user.
    """
    design = build_design_service(db).get_design_for_customer(
        design_id,
        current_user.id,
    )
    if design is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found",
        )

    return DesignRead.model_validate(design)
