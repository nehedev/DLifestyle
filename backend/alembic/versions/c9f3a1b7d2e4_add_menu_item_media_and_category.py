"""add the menu item category and image fields

Revision ID: c9f3a1b7d2e4
Revises: b7c41e9d2a05
Create Date: 2026-10-03 22:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9f3a1b7d2e4"
down_revision: str | Sequence[str] | None = "b7c41e9d2a05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UNCATEGORIZED = "Uncategorized"


def upgrade() -> None:
    """Add category, image_url, and image_alt to menu_items.

    category is required. Existing rows are backfilled with a placeholder
    through a server default, which is then dropped so the application must
    supply the value.
    """
    op.add_column(
        "menu_items",
        sa.Column(
            "category",
            sa.Text(),
            nullable=False,
            server_default=sa.text(f"'{_UNCATEGORIZED}'"),
        ),
    )
    op.add_column("menu_items", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("menu_items", sa.Column("image_alt", sa.Text(), nullable=True))
    op.alter_column("menu_items", "category", server_default=None)


def downgrade() -> None:
    """Drop category, image_url, and image_alt from menu_items."""
    op.drop_column("menu_items", "image_alt")
    op.drop_column("menu_items", "image_url")
    op.drop_column("menu_items", "category")
