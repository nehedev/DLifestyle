"""rename auth0_sub to provider_sub and add user roles

Revision ID: d1e2f3a4b5c6
Revises: c9f3a1b7d2e4
Create Date: 2026-10-04 01:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "c9f3a1b7d2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTH0_SUB_CONSTRAINT = "uq_users_auth0_sub"
_PROVIDER_SUB_CONSTRAINT = "uq_users_provider_sub"
_ROLE_CONSTRAINT = "ck_users_valid_role"


def upgrade() -> None:
    """Move to Google subjects and add the stored role."""
    op.alter_column("users", "auth0_sub", new_column_name="provider_sub")
    op.execute(
        f"ALTER TABLE users RENAME CONSTRAINT {_AUTH0_SUB_CONSTRAINT} "
        f"TO {_PROVIDER_SUB_CONSTRAINT}"
    )
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'user'"),
        ),
    )
    op.create_check_constraint(
        _ROLE_CONSTRAINT, "users", sa.text("role IN ('user', 'admin')")
    )


def downgrade() -> None:
    """Drop the role and move the subject column back."""
    op.drop_constraint(_ROLE_CONSTRAINT, "users", type_="check")
    op.drop_column("users", "role")
    op.execute(
        f"ALTER TABLE users RENAME CONSTRAINT {_PROVIDER_SUB_CONSTRAINT} "
        f"TO {_AUTH0_SUB_CONSTRAINT}"
    )
    op.alter_column("users", "provider_sub", new_column_name="auth0_sub")
