"""add server-side cart

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-10-06 05:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: str | Sequence[str] | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KIND_CHECK = "valid_kind"
_QUANTITY_CHECK = "quantity_positive"
_TARGET_CHECK = "target_matches_kind"
_USER_FK = "fk_cart_items_user_id_users"
_MENU_FK = "fk_cart_items_menu_item_id_menu_items"
_SERVICE_FK = "fk_cart_items_service_id_services"


def upgrade() -> None:
    """Create the per-user cart table."""
    op.create_table(
        "cart_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("menu_item_id", sa.BigInteger(), nullable=True),
        sa.Column("service_id", sa.BigInteger(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("preferred_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=_USER_FK, ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"], name=_MENU_FK),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], name=_SERVICE_FK),
        sa.CheckConstraint("kind IN ('food', 'service')", name=_KIND_CHECK),
        sa.CheckConstraint("quantity > 0", name=_QUANTITY_CHECK),
        sa.CheckConstraint(
            "(kind = 'food' AND menu_item_id IS NOT NULL "
            "AND service_id IS NULL AND preferred_date IS NULL) OR "
            "(kind = 'service' AND service_id IS NOT NULL "
            "AND menu_item_id IS NULL)",
            name=_TARGET_CHECK,
        ),
    )
    op.create_index("ix_cart_items_user_id", "cart_items", ["user_id"])
    op.create_index(
        "uq_cart_items_food",
        "cart_items",
        ["user_id", "menu_item_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'food'"),
    )


def downgrade() -> None:
    """Drop the cart table."""
    op.drop_index("uq_cart_items_food", table_name="cart_items")
    op.drop_index("ix_cart_items_user_id", table_name="cart_items")
    op.drop_table("cart_items")
