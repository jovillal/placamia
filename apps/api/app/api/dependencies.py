from app.core.config import settings
from app.core.database import get_db
from app.domain.provider_adapter import LocalMockProviderAdapter
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthenticationError, AuthService
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

bearer_scheme = HTTPBearer(auto_error=False)


async def get_provider_adapter():
    """Return the provider adapter used for backend-owned catalog decisions.

    Returns:
        The deterministic local/mock provider adapter used for MVP backend
        development until a real provider adapter is implemented.

    Side effects:
        None.
    """
    return LocalMockProviderAdapter()


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Resolve an optional authenticated user from a bearer token.

    Args:
        credentials: Authorization credentials parsed from the request header.
        db: SQLAlchemy session provided by FastAPI dependency injection.

    Returns:
        The active user associated with a supplied verified bearer token, or
        None when the request supplies no credentials.

    Side effects:
        Reads user data from the database.

    Raises:
        HTTPException: When supplied credentials are invalid or reference an
            inactive or missing user.
    """
    unauthorized_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        return None

    auth_service = AuthService(settings.AUTH_TOKEN_SECRET)

    try:
        subject = auth_service.verify_access_token(credentials.credentials)
    except AuthenticationError as exc:
        raise unauthorized_exception from exc

    user_repository = UserRepository(db)
    user = user_repository.get_user_by_id(subject.user_id)

    if user is None or not user.is_active:
        raise unauthorized_exception

    return user


async def get_current_user(
    current_user: User | None = Depends(get_optional_current_user),
) -> User:
    """Require and return the authenticated current user.

    Args:
        current_user: Optional active user resolved from bearer credentials.

    Returns:
        The authenticated active user.

    Side effects:
        None beyond the optional authentication dependency's database read.

    Raises:
        HTTPException: When the request supplies no authentication credentials.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def require_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require the authenticated current user to have the admin role.

    Args:
        current_user: Active user resolved from the authenticated request.

    Returns:
        The authenticated admin user.

    Side effects:
        None.

    Raises:
        HTTPException: When the current user is authenticated but not an admin.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges are required",
        )

    return current_user
