"""replace the products catalog with the menu and services catalog

Revision ID: b7c41e9d2a05
Revises: 174baad456c0
Create Date: 2026-10-03 00:12:44.117903

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c41e9d2a05"
down_revision: str | Sequence[str] | None = "174baad456c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PAYMENTS_ORDER_FOREIGN_KEY = "fk_payments_order_id_orders"


def upgrade() -> None:
    """Drop the products catalog and build the menu, services, and store tables."""
    op.drop_constraint(_PAYMENTS_ORDER_FOREIGN_KEY, "payments", type_="foreignkey")
    op.create_check_constraint(
        op.f("ck_payments_amount_minor_nonnegative"),
        "payments",
        sa.text("amount_minor >= 0"),
    )
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("products")

    op.create_table(
        "menu_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_minor", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_sold_out", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "price_minor >= 0", name=op.f("ck_menu_items_price_minor_nonnegative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_items")),
    )
    op.create_table(
        "services",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
    )
    op.create_table(
        "store_settings",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("delivery_fee_minor", sa.Integer(), nullable=False),
        sa.Column("order_cutoff_time", sa.Time(), nullable=False),
        sa.Column("max_advance_days", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_store_settings_singleton_row")),
        sa.CheckConstraint(
            "delivery_fee_minor >= 0",
            name=op.f("ck_store_settings_delivery_fee_minor_nonnegative"),
        ),
        sa.CheckConstraint(
            "max_advance_days >= 0",
            name=op.f("ck_store_settings_max_advance_days_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_store_settings")),
    )
    op.create_table(
        "menu_item_days",
        sa.Column("menu_item_id", sa.BigInteger(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "weekday BETWEEN 1 AND 7", name=op.f("ck_menu_item_days_weekday_iso_range")
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"],
            ["menu_items.id"],
            name=op.f("fk_menu_item_days_menu_item_id_menu_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "menu_item_id", "weekday", name=op.f("pk_menu_item_days")
        ),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("fulfillment_type", sa.Text(), nullable=False),
        sa.Column("fulfillment_date", sa.Date(), nullable=False),
        sa.Column("contact", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("items_total_minor", sa.Integer(), nullable=False),
        sa.Column("delivery_fee_minor", sa.Integer(), nullable=False),
        sa.Column("total_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'preparing', 'ready', 'completed', "
            "'cancelled')",
            name=op.f("ck_orders_valid_status"),
        ),
        sa.CheckConstraint(
            "fulfillment_type IN ('delivery', 'pickup')",
            name=op.f("ck_orders_valid_fulfillment_type"),
        ),
        sa.CheckConstraint(
            "items_total_minor >= 0", name=op.f("ck_orders_items_total_nonnegative")
        ),
        sa.CheckConstraint(
            "delivery_fee_minor >= 0", name=op.f("ck_orders_delivery_fee_nonnegative")
        ),
        sa.CheckConstraint(
            "total_minor >= 0", name=op.f("ck_orders_total_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_orders_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_orders_user_id_idempotency_key"
        ),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"], unique=False)
    op.create_table(
        "order_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("menu_item_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_minor", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "quantity > 0", name=op.f("ck_order_items_quantity_positive")
        ),
        sa.CheckConstraint(
            "unit_price_minor >= 0",
            name=op.f("ck_order_items_unit_price_minor_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"],
            ["menu_items.id"],
            name=op.f("fk_order_items_menu_item_id_menu_items"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_items_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
        sa.UniqueConstraint(
            "order_id", "menu_item_id", name="uq_order_items_order_item"
        ),
    )
    op.create_table(
        "service_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("service_id", sa.BigInteger(), nullable=False),
        sa.Column("preferred_date", sa.Date(), nullable=True),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("contact_phone", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("quoted_amount_minor", sa.Integer(), nullable=True),
        sa.Column("owner_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('requested', 'contacted', 'confirmed', 'completed', "
            "'cancelled')",
            name=op.f("ck_service_requests_valid_status"),
        ),
        sa.CheckConstraint(
            "quoted_amount_minor IS NULL OR quoted_amount_minor >= 0",
            name=op.f("ck_service_requests_quoted_amount_minor_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_service_requests_service_id_services"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_service_requests_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_requests")),
    )
    op.create_index(
        "ix_service_requests_status",
        "service_requests",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_service_requests_user_id",
        "service_requests",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        _PAYMENTS_ORDER_FOREIGN_KEY,
        "payments",
        "orders",
        ["order_id"],
        ["id"],
    )


def downgrade() -> None:
    """Drop the menu, services, and store tables and restore the products catalog."""
    op.drop_constraint(_PAYMENTS_ORDER_FOREIGN_KEY, "payments", type_="foreignkey")
    op.drop_constraint(
        op.f("ck_payments_amount_minor_nonnegative"), "payments", type_="check"
    )
    op.drop_index("ix_service_requests_user_id", table_name="service_requests")
    op.drop_index("ix_service_requests_status", table_name="service_requests")
    op.drop_table("service_requests")
    op.drop_table("order_items")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_table("orders")
    op.drop_table("menu_item_days")
    op.drop_table("store_settings")
    op.drop_table("services")
    op.drop_table("menu_items")

    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("price_minor", sa.Integer(), nullable=False),
        sa.Column("stock_quantity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "price_minor >= 0", name=op.f("ck_products_price_minor_nonnegative")
        ),
        sa.CheckConstraint(
            "stock_quantity >= 0",
            name=op.f("ck_products_stock_quantity_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("total_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "shipping_address", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'shipped', 'cancelled', 'refunded')",
            name=op.f("ck_orders_valid_status"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_orders_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_orders_user_id_idempotency_key"
        ),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"], unique=False)
    op.create_table(
        "order_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_minor", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "quantity > 0", name=op.f("ck_order_items_quantity_positive")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_items_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_order_items_product_id_products"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
        sa.UniqueConstraint(
            "order_id", "product_id", name="uq_order_items_order_product"
        ),
    )
    op.create_foreign_key(
        _PAYMENTS_ORDER_FOREIGN_KEY,
        "payments",
        "orders",
        ["order_id"],
        ["id"],
    )
