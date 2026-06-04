from datetime import datetime

from app.core.database import Base
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column


class UserRole:
    """Supported backend-owned user roles.

    Role values are stored on user records and must be read from the database
    after authentication. They are never accepted from frontend payloads as
    proof of authorization.
    """

    USER = "user"
    ADMIN = "admin"


class User(Base):
    """Application user account.

    The model maps to the `users` table and stores contact information,
    backend-owned role, activation status, and database-managed timestamps.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=UserRole.USER,
        server_default=UserRole.USER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
