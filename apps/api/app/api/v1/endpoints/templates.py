from app.core.database import get_db
from app.repositories.template_field_repository import TemplateFieldRepository
from app.repositories.template_repository import TemplateRepository
from app.schemas.template import (
    TemplateDetailRead,
    TemplateFieldRead,
    TemplateListResponse,
    TemplateSummaryRead,
)
from app.services.template_field_service import TemplateFieldService
from app.services.template_service import TemplateService
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get(
    "",
    response_model=TemplateListResponse,
    summary="List Templates",
    description=(
        "Returns active reusable Templates as customer-safe summaries ordered "
        "by name and identifier. TemplateField definitions are available only "
        "from the Template detail endpoint."
    ),
)
async def list_templates(
    db: Session = Depends(get_db),
) -> TemplateListResponse:
    """Return active Templates for public rules-based customization browsing.

    Args:
        db: SQLAlchemy session provided by FastAPI dependency injection.

    Returns:
        Active customer-safe Template summaries under the `data` key.

    Side effects:
        None.
    """
    template_service = TemplateService(TemplateRepository(db))

    return TemplateListResponse(
        data=[
            TemplateSummaryRead.model_validate(template)
            for template in template_service.list_templates()
        ]
    )


@router.get(
    "/{template_id}",
    response_model=TemplateDetailRead,
    summary="Get Template",
    description=(
        "Returns one active Template and its active backend-owned "
        "customization fields in deterministic display order."
    ),
    responses={404: {"description": "Template not found"}},
)
async def get_template(
    template_id: int,
    db: Session = Depends(get_db),
) -> TemplateDetailRead:
    """Return one active Template with customer-facing active fields.

    Args:
        template_id: Template identifier from the request path.
        db: SQLAlchemy session provided by FastAPI dependency injection.

    Returns:
        The matching public Template detail response.

    Side effects:
        None.

    Raises:
        HTTPException: When the Template is unknown or inactive.
    """
    template_service = TemplateService(TemplateRepository(db))
    template = template_service.get_template(template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    field_service = TemplateFieldService(TemplateFieldRepository(db))
    fields = field_service.list_fields_for_template(template_id)

    return TemplateDetailRead(
        id=template.id,
        name=template.name,
        description=template.description,
        fields=[TemplateFieldRead.model_validate(field) for field in fields],
    )
