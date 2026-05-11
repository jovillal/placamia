from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.template import Template


class Design(Base):
    """Persisted customized signage Design derived from one Template.

    The model maps to the `designs` table and stores backend-validated
    customization values for future pricing, order generation, and provider
    handoff. It does not validate submitted customization data, redefine
    TemplateField rules, calculate prices, or expose editing behavior.
    """

    __tablename__ = "designs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("templates.id"),
        nullable=False,
        index=True,
    )
    customization_values: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
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
    template: Mapped["Template"] = relationship(
        "Template",
        back_populates="designs",
    )
