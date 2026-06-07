"""create orders and order items tables

Revision ID: 8c1d2e3f4a5b
Revises: 5d0f6a7b8c9d
Create Date: 2026-06-07 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c1d2e3f4a5b"
down_revision: Union[str, Sequence[str], None] = "5d0f6a7b8c9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=64), server_default="draft", nullable=False
        ),
        sa.Column("cancellation_requested_from", sa.String(length=64), nullable=True),
        sa.Column("subtotal_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "discount_amount",
            sa.Numeric(12, 2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column(
            "tax_amount",
            sa.Numeric(12, 2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "currency", sa.String(length=3), server_default="COP", nullable=False
        ),
        sa.Column("payment_provider_reference", sa.String(length=255), nullable=True),
        sa.Column("payment_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_provider_id", sa.String(length=100), nullable=True),
        sa.Column("provider_handoff_reference", sa.String(length=255), nullable=True),
        sa.Column(
            "provider_handoff_sent_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("terms_policy_version", sa.String(length=100), nullable=True),
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
        sa.CheckConstraint(
            "status IN ("
            "'draft', "
            "'confirmed', "
            "'sent_to_provider', "
            "'accepted', "
            "'in_production', "
            "'ready_for_pickup', "
            "'shipped', "
            "'delivered', "
            "'cancellation_requested', "
            "'cancelled'"
            ")",
            name="ck_orders_status_supported",
        ),
        sa.CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name="ck_orders_currency_iso_uppercase",
        ),
        sa.CheckConstraint(
            "subtotal_amount >= 0",
            name="ck_orders_subtotal_amount_nonnegative",
        ),
        sa.CheckConstraint(
            "discount_amount >= 0",
            name="ck_orders_discount_amount_nonnegative",
        ),
        sa.CheckConstraint("tax_amount >= 0", name="ck_orders_tax_amount_nonnegative"),
        sa.CheckConstraint(
            "total_amount >= 0",
            name="ck_orders_total_amount_nonnegative",
        ),
        sa.CheckConstraint(
            "("
            "status = 'cancellation_requested' "
            "AND cancellation_requested_from IN ("
            "'confirmed', 'accepted', 'in_production'"
            ")"
            ") OR ("
            "status != 'cancellation_requested' "
            "AND cancellation_requested_from IS NULL"
            ")",
            name="ck_orders_cancellation_requested_from_matches_status",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_orders_id"), "orders", ["id"])
    op.create_index(op.f("ix_orders_customer_id"), "orders", ["customer_id"])
    op.create_index(op.f("ix_orders_status"), "orders", ["status"])
    op.create_index(
        op.f("ix_orders_payment_provider_reference"),
        "orders",
        ["payment_provider_reference"],
    )
    op.create_index(
        op.f("ix_orders_provider_handoff_reference"),
        "orders",
        ["provider_handoff_reference"],
    )

    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(length=32), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("kit_id", sa.Integer(), nullable=True),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("design_id", sa.Integer(), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("customer_safe_description", sa.Text(), nullable=True),
        sa.Column("selected_options", sa.JSON(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_subtotal_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "line_discount_amount",
            sa.Numeric(12, 2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column(
            "line_tax_amount",
            sa.Numeric(12, 2),
            server_default="0.00",
            nullable=False,
        ),
        sa.Column("line_total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "currency", sa.String(length=3), server_default="COP", nullable=False
        ),
        sa.Column("assigned_provider_id", sa.String(length=100), nullable=False),
        sa.Column("provider_pricing_reference", sa.String(length=255), nullable=True),
        sa.Column("provider_payload_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "item_type IN ('product', 'kit', 'design')",
            name="ck_order_items_item_type_supported",
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_order_items_quantity_positive",
        ),
        sa.CheckConstraint(
            "currency = upper(currency) AND length(currency) = 3",
            name="ck_order_items_currency_iso_uppercase",
        ),
        sa.CheckConstraint(
            "unit_price_amount >= 0",
            name="ck_order_items_unit_price_amount_nonnegative",
        ),
        sa.CheckConstraint(
            "line_subtotal_amount >= 0",
            name="ck_order_items_line_subtotal_amount_nonnegative",
        ),
        sa.CheckConstraint(
            "line_discount_amount >= 0",
            name="ck_order_items_line_discount_amount_nonnegative",
        ),
        sa.CheckConstraint(
            "line_tax_amount >= 0",
            name="ck_order_items_line_tax_amount_nonnegative",
        ),
        sa.CheckConstraint(
            "line_total_amount >= 0",
            name="ck_order_items_line_total_amount_nonnegative",
        ),
        sa.ForeignKeyConstraint(["design_id"], ["designs.id"]),
        sa.ForeignKeyConstraint(["kit_id"], ["kits.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_items_id"), "order_items", ["id"])
    op.create_index(op.f("ix_order_items_order_id"), "order_items", ["order_id"])
    op.create_index(op.f("ix_order_items_item_type"), "order_items", ["item_type"])
    op.create_index(op.f("ix_order_items_product_id"), "order_items", ["product_id"])
    op.create_index(op.f("ix_order_items_kit_id"), "order_items", ["kit_id"])
    op.create_index(op.f("ix_order_items_template_id"), "order_items", ["template_id"])
    op.create_index(op.f("ix_order_items_design_id"), "order_items", ["design_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_order_items_design_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_template_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_kit_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_product_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_item_type"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_order_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_id"), table_name="order_items")
    op.drop_table("order_items")

    op.drop_index(op.f("ix_orders_provider_handoff_reference"), table_name="orders")
    op.drop_index(op.f("ix_orders_payment_provider_reference"), table_name="orders")
    op.drop_index(op.f("ix_orders_status"), table_name="orders")
    op.drop_index(op.f("ix_orders_customer_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_id"), table_name="orders")
    op.drop_table("orders")
