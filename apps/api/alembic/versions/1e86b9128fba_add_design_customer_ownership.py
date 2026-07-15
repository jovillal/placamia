"""add design customer ownership

Revision ID: 1e86b9128fba
Revises: 1f2a3b4c5d6e
Create Date: 2026-07-15 10:23:14.581801

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1e86b9128fba"
down_revision: Union[str, Sequence[str], None] = "1f2a3b4c5d6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add required Design ownership without fabricating legacy owners.

    Raises:
        RuntimeError: When existing Design rows require an explicit ownership
            backfill decision before this migration can proceed.
    """
    existing_design_count = (
        op.get_bind().execute(sa.text("SELECT count(*) FROM designs")).scalar_one()
    )
    if existing_design_count:
        raise RuntimeError(
            "Cannot add required designs.customer_id while Design rows exist; "
            "backfill explicit customer ownership before retrying."
        )

    op.add_column("designs", sa.Column("customer_id", sa.Integer(), nullable=False))
    op.create_index(
        op.f("ix_designs_customer_id"),
        "designs",
        ["customer_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_designs_customer_id_users",
        "designs",
        "users",
        ["customer_id"],
        ["id"],
    )


def downgrade() -> None:
    """Remove required Design ownership."""
    op.drop_constraint(
        "fk_designs_customer_id_users",
        "designs",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_designs_customer_id"), table_name="designs")
    op.drop_column("designs", "customer_id")
