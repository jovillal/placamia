from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.design import Design
    from app.models.template_field import TemplateField


class Template(Base):
    """Reusable base design used to create user-specific Designs.

    The model maps to the `templates` table and stores catalog-level template
    metadata only. User customization values belong to future Design records,
    not to Template.
    """

    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    template_fields: Mapped[list[TemplateField]] = relationship(
        "TemplateField",
        back_populates="template",
    )
    designs: Mapped[list[Design]] = relationship(
        "Design",
        back_populates="template",
    )
