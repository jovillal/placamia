"""create kits and kit items tables

Revision ID: 4a2b8c9d0e1f
Revises: 2b8f3c4d5e6a
Create Date: 2026-05-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4a2b8c9d0e1f"
down_revision: Union[str, Sequence[str], None] = "2b8f3c4d5e6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "kits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kits_id"), "kits", ["id"])
    op.create_index(op.f("ix_kits_name"), "kits", ["name"])

    op.create_table(
        "kit_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kit_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["kit_id"], ["kits.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kit_items_id"), "kit_items", ["id"])
    op.create_index(op.f("ix_kit_items_kit_id"), "kit_items", ["kit_id"])
    op.create_index(op.f("ix_kit_items_product_id"), "kit_items", ["product_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_kit_items_product_id"), table_name="kit_items")
    op.drop_index(op.f("ix_kit_items_kit_id"), table_name="kit_items")
    op.drop_index(op.f("ix_kit_items_id"), table_name="kit_items")
    op.drop_table("kit_items")
    op.drop_index(op.f("ix_kits_name"), table_name="kits")
    op.drop_index(op.f("ix_kits_id"), table_name="kits")
    op.drop_table("kits")
