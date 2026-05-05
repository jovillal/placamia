"""create template fields table

Revision ID: 2b8f3c4d5e6a
Revises: 9f7d0b6a2c1e
Create Date: 2026-05-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2b8f3c4d5e6a"
down_revision: Union[str, Sequence[str], None] = "9f7d0b6a2c1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "template_fields",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("field_type", sa.String(length=100), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("allowed_values", sa.JSON(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
    op.create_index(
        op.f("ix_template_fields_field_name"),
        "template_fields",
        ["field_name"],
    )
    op.create_index(op.f("ix_template_fields_id"), "template_fields", ["id"])
    op.create_index(
        op.f("ix_template_fields_template_id"),
        "template_fields",
        ["template_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_template_fields_template_id"), table_name="template_fields")
    op.drop_index(op.f("ix_template_fields_id"), table_name="template_fields")
    op.drop_index(op.f("ix_template_fields_field_name"), table_name="template_fields")
    op.drop_table("template_fields")
