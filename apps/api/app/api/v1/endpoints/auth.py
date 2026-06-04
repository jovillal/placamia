from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserRead
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user",
    description=("Returns the authenticated current user resolved from the bearer token."),
)
async def read_current_user(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """Return the authenticated current user.

    Args:
        current_user: Active user resolved from the authenticated request.

    Returns:
        The authenticated user's safe public account fields.

    Side effects:
        None.
    """
    return UserRead.model_validate(current_user)
