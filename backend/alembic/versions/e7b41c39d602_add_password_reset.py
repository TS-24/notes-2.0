"""Password resets: one-time tokens, and when a password last changed

A reset link is issued from the account page by the superuser and handed over
in person, the way an invite code is (api/invites.py). Nothing is emailed, so
what has to be stored is only the proof that a link exists and has not been
spent: `password_reset_tokens` holds the SHA-256 of the token and never the
token. That is deliberate and is why the link, unlike an invite code, is shown
once and cannot be listed back — an invite is worth a new account bound to one
address, a reset link is worth an existing account.

`users.password_changed_at` is nullable and needs no backfill: NULL reads as
"never reset", which is every account on this database today. It is what lets a
reset also end the sessions that predated it — `api/deps.py` refuses any token
issued before it. Backfilling it to `now()` instead would sign everyone out the
moment this migration ran, which is not what a schema change should do.

Added inside `op.batch_alter_table` because SQLite cannot ALTER and the test
suite runs on SQLite; `render_as_batch` in env.py only covers autogeneration.

The downgrade is real rather than a stub, because CI round-trips
upgrade -> downgrade -> upgrade and that is the only place a migration runs at
all (the test suite builds its schema with create_all).

Revision ID: e7b41c39d602
Revises: c9f2a71e4d38
Create Date: 2026-08-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7b41c39d602"
down_revision: Union[str, Sequence[str], None] = "c9f2a71e4d38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # SHA-256 hex of the issued token: 64 characters exactly.
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
    # token_hash is read on every reset attempt; user_id is for retiring an
    # account's outstanding links, and expires_at for pruning.
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
