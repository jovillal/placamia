"""add payment webhook replay keys

Revision ID: 1f2a3b4c5d6e
Revises: d130aa829359
Create Date: 2026-06-30 10:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1f2a3b4c5d6e"
down_revision: Union[str, Sequence[str], None] = "d130aa829359"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column(
            "source",
            sa.String(length=64),
            server_default="payment_provider_webhook",
            nullable=False,
        ),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("payment_id", sa.Integer(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(
        op.f("ix_payment_webhook_events_id"),
        "payment_webhook_events",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_webhook_events_order_id"),
        "payment_webhook_events",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_webhook_events_payment_id"),
        "payment_webhook_events",
        ["payment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_webhook_events_source"),
        "payment_webhook_events",
        ["source"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_payments_order_provider_reference",
        "payments",
        ["order_id", "payment_provider_reference"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_payments_order_provider_reference",
        "payments",
        type_="unique",
    )
    op.drop_index(
        op.f("ix_payment_webhook_events_source"),
        table_name="payment_webhook_events",
    )
    op.drop_index(
        op.f("ix_payment_webhook_events_payment_id"),
        table_name="payment_webhook_events",
    )
    op.drop_index(
        op.f("ix_payment_webhook_events_order_id"),
        table_name="payment_webhook_events",
    )
    op.drop_index(
        op.f("ix_payment_webhook_events_id"),
        table_name="payment_webhook_events",
    )
    op.drop_table("payment_webhook_events")
