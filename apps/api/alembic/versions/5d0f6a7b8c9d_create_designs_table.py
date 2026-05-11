"""create designs table

Revision ID: 5d0f6a7b8c9d
Revises: 4a2b8c9d0e1f
Create Date: 2026-05-11 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5d0f6a7b8c9d"
down_revision: Union[str, Sequence[str], None] = "4a2b8c9d0e1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "designs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("customization_values", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_designs_id"), "designs", ["id"])
    op.create_index(op.f("ix_designs_template_id"), "designs", ["template_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_designs_template_id"), table_name="designs")
    op.drop_index(op.f("ix_designs_id"), table_name="designs")
    op.drop_table("designs")
