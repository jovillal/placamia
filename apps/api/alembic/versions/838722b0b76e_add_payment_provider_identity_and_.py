"""add payment provider identity and history

Revision ID: 838722b0b76e
Revises: 68a133510971
Create Date: 2026-07-22 16:03:36.322661

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "838722b0b76e"
down_revision: Union[str, Sequence[str], None] = "68a133510971"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "payment_provider_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column(
            "provider_transaction_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("provider_status", sa.String(length=64), nullable=False),
        sa.Column("normalized_status", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "normalized_status IN ('initiated', 'pending', 'requires_action', "
            "'verified', 'failed', 'cancelled', 'expired')",
            name="ck_payment_provider_transactions_status_supported",
        ),
        sa.CheckConstraint(
            "amount >= 0",
            name="ck_payment_provider_transactions_amount_nonnegative",
        ),
        sa.CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name="ck_payment_provider_transactions_currency_iso_uppercase",
        ),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_code",
            "provider_transaction_reference",
            name="uq_payment_provider_transactions_provider_reference",
        ),
    )
    op.create_index(
        op.f("ix_payment_provider_transactions_id"),
        "payment_provider_transactions",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_provider_transactions_payment_id"),
        "payment_provider_transactions",
        ["payment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_provider_transactions_provider_code"),
        "payment_provider_transactions",
        ["provider_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_provider_transactions_provider_transaction_reference"),
        "payment_provider_transactions",
        ["provider_transaction_reference"],
        unique=False,
    )
    op.create_table(
        "payment_provider_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("payment_provider_transaction_id", sa.Integer(), nullable=True),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column(
            "provider_event_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("provider_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.ForeignKeyConstraint(
            ["payment_provider_transaction_id"],
            ["payment_provider_transactions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_code",
            "provider_event_reference",
            name="uq_payment_provider_events_provider_reference",
        ),
    )
    op.create_index(
        op.f("ix_payment_provider_events_id"),
        "payment_provider_events",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_provider_events_payment_id"),
        "payment_provider_events",
        ["payment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_provider_events_payment_provider_transaction_id"),
        "payment_provider_events",
        ["payment_provider_transaction_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_provider_events_provider_code"),
        "payment_provider_events",
        ["provider_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_provider_events_provider_event_reference"),
        "payment_provider_events",
        ["provider_event_reference"],
        unique=False,
    )
    op.add_column(
        "payments",
        sa.Column("provider_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("merchant_reference", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column(
            "provider_checkout_reference",
            sa.String(length=255),
            nullable=True,
        ),
    )
    op.add_column(
        "payments",
        sa.Column("checkout_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_payments_merchant_reference"),
        "payments",
        ["merchant_reference"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payments_provider_code"),
        "payments",
        ["provider_code"],
        unique=False,
    )
    op.execute(
        sa.text(
            """
            UPDATE payments
            SET provider_code = 'legacy_generic',
                merchant_reference = 'legacy-payment-' || CAST(id AS VARCHAR(32))
            WHERE provider_code IS NULL OR merchant_reference IS NULL
            """
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_payments_provider_code"), table_name="payments")
    op.drop_index(op.f("ix_payments_merchant_reference"), table_name="payments")
    op.drop_column("payments", "checkout_expires_at")
    op.drop_column("payments", "provider_checkout_reference")
    op.drop_column("payments", "merchant_reference")
    op.drop_column("payments", "provider_code")
    op.drop_index(
        op.f("ix_payment_provider_events_provider_event_reference"),
        table_name="payment_provider_events",
    )
    op.drop_index(
        op.f("ix_payment_provider_events_provider_code"),
        table_name="payment_provider_events",
    )
    op.drop_index(
        op.f("ix_payment_provider_events_payment_provider_transaction_id"),
        table_name="payment_provider_events",
    )
    op.drop_index(
        op.f("ix_payment_provider_events_payment_id"),
        table_name="payment_provider_events",
    )
    op.drop_index(
        op.f("ix_payment_provider_events_id"),
        table_name="payment_provider_events",
    )
    op.drop_table("payment_provider_events")
    op.drop_index(
        op.f("ix_payment_provider_transactions_provider_transaction_reference"),
        table_name="payment_provider_transactions",
    )
    op.drop_index(
        op.f("ix_payment_provider_transactions_provider_code"),
        table_name="payment_provider_transactions",
    )
    op.drop_index(
        op.f("ix_payment_provider_transactions_payment_id"),
        table_name="payment_provider_transactions",
    )
    op.drop_index(
        op.f("ix_payment_provider_transactions_id"),
        table_name="payment_provider_transactions",
    )
    op.drop_table("payment_provider_transactions")
