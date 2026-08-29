"""add password reset tokens and users.password_changed_at

Revision ID: a3d8f1c92b47
Revises: f2b6c48e0d19
Create Date: 2026-08-29

One table for the self-service reset flow (app/api/auth.py::forgot_password /
reset_password) and one nullable column on users.

`password_reset_tokens` holds only the SHA-256 of the emailed token — the token
itself is never stored, the same arrangement `users.password_hash` has. `used_at`
being set is what "already spent" means, mirroring `invite_codes`.

`users.password_changed_at` is nullable and needs no backfill: NULL reads as
"never reset", which is every existing account. It is added inside
`op.batch_alter_table` because SQLite cannot ALTER and the test suite runs on
SQLite — `render_as_batch` in env.py only covers autogeneration.

The downgrade is real rather than a stub: CI round-trips
upgrade -> downgrade -> upgrade, and that is the only place a migration runs at
all (the test suite builds its schema with create_all).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3d8f1c92b47"
down_revision: Union[str, Sequence[str], None] = "f2b6c48e0d19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # SHA-256 hex of the emailed token: 64 characters exactly.
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    # token_hash is looked up on every reset attempt; user_id and expires_at are
    # for invalidating a user's outstanding links and for pruning.
    op.create_index(
        "ix_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"]
    )
    op.create_index(
        "ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"]
    )

    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("password_changed_at")

    op.drop_index(
        "ix_password_reset_tokens_expires_at", table_name="password_reset_tokens"
    )
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_index(
        "ix_password_reset_tokens_token_hash", table_name="password_reset_tokens"
    )
    op.drop_table("password_reset_tokens")
