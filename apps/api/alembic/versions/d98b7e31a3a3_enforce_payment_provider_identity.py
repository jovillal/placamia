"""enforce payment provider identity

Revision ID: d98b7e31a3a3
Revises: 838722b0b76e
Create Date: 2026-07-22 16:05:42.777615

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d98b7e31a3a3"
down_revision: Union[str, Sequence[str], None] = "838722b0b76e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    invalid_identity_count = bind.execute(
        sa.text(
            """
            SELECT count(*)
            FROM payments
            WHERE provider_code IS NULL
               OR merchant_reference IS NULL
               OR merchant_reference LIKE '%-uncommitted-%'
            """
        )
    ).scalar_one()
    if invalid_identity_count:
        raise RuntimeError(
            "Payment provider identity backfill or writer compatibility is "
            "incomplete; refusing to apply contract constraints."
        )

    duplicate_identity_count = bind.execute(
        sa.text(
            """
            SELECT count(*)
            FROM (
                SELECT provider_code, merchant_reference
                FROM payments
                GROUP BY provider_code, merchant_reference
                HAVING count(*) > 1
            ) AS duplicate_payment_identities
            """
        )
    ).scalar_one()
    if duplicate_identity_count:
        raise RuntimeError(
            "Duplicate Payment provider identities exist; refusing to apply "
            "the uniqueness constraint."
        )

    op.alter_column(
        "payments",
        "provider_code",
        existing_type=sa.VARCHAR(length=64),
        nullable=False,
    )
    op.alter_column(
        "payments",
        "merchant_reference",
        existing_type=sa.VARCHAR(length=255),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_payments_provider_merchant_reference",
        "payments",
        ["provider_code", "merchant_reference"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_payments_provider_merchant_reference",
        "payments",
        type_="unique",
    )
    op.alter_column(
        "payments",
        "merchant_reference",
        existing_type=sa.VARCHAR(length=255),
        nullable=True,
    )
    op.alter_column(
        "payments",
        "provider_code",
        existing_type=sa.VARCHAR(length=64),
        nullable=True,
    )
