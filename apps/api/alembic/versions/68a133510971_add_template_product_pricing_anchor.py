"""add template product pricing anchor

Revision ID: 68a133510971
Revises: 1e86b9128fba
Create Date: 2026-07-15 12:41:27.380905

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "68a133510971"
down_revision: Union[str, Sequence[str], None] = "1e86b9128fba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add required Product pricing ownership without fabricating mappings."""
    existing_template_count = (
        op.get_bind().execute(sa.text("SELECT count(*) FROM templates")).scalar_one()
    )
    if existing_template_count:
        raise RuntimeError(
            "Cannot add required templates.product_id while Template rows exist; "
            "backfill explicit Product mappings before retrying."
        )

    op.add_column(
        "templates",
        sa.Column("product_id", sa.Integer(), nullable=False),
    )
    op.create_index(
        op.f("ix_templates_product_id"),
        "templates",
        ["product_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_templates_product_id_products",
        "templates",
        "products",
        ["product_id"],
        ["id"],
    )


def downgrade() -> None:
    """Remove required Template Product pricing ownership."""
    op.drop_constraint(
        "fk_templates_product_id_products",
        "templates",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_templates_product_id"), table_name="templates")
    op.drop_column("templates", "product_id")
