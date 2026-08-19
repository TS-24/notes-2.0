"""Add user passwords, timestamps and invite codes

Revision ID: e4a17c8b3f92
Revises: d5a82f1c9e37
Create Date: 2026-08-19

`password_hash` cannot be added NOT NULL in one step, because rows already
exist and no password can be invented for them. So it arrives nullable, gets
backfilled with "!" — a value no argon2 hash can equal, making those accounts
unloggable-into rather than open — and is tightened afterwards.

The tightening runs inside `op.batch_alter_table` because SQLite cannot ALTER
a column and the test suite runs on SQLite. `render_as_batch` in env.py only
covers autogeneration; a hand-written migration has to ask for batch mode
itself.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e4a17c8b3f92"
down_revision: Union[str, Sequence[str], None] = "d5a82f1c9e37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UNUSABLE_PASSWORD_HASH = "!"


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))
        batch.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            )
        )

    op.execute(
        sa.text("UPDATE users SET password_hash = :h WHERE password_hash IS NULL").bindparams(
            h=UNUSABLE_PASSWORD_HASH
        )
    )

    with op.batch_alter_table("users") as batch:
        batch.alter_column("password_hash", existing_type=sa.String(length=255), nullable=False)

    op.create_table(
        "invite_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["used_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_invite_codes_code", "invite_codes", ["code"])


def downgrade() -> None:
    op.drop_index("ix_invite_codes_code", table_name="invite_codes")
    op.drop_table("invite_codes")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("created_at")
        batch.drop_column("password_hash")
