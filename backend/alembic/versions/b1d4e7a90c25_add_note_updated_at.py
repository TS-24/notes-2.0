"""Add notes.updated_at

Backs "where you left off": the landing page opens the most recently touched
note, and opening a note counts as a touch.

Revision ID: b1d4e7a90c25
Revises: 0442f6ed1d44
Create Date: 2026-07-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1d4e7a90c25"
down_revision: Union[str, Sequence[str], None] = "0442f6ed1d44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default fills existing rows; seed it from created_at afterwards so
    # notes that already exist keep a sensible order instead of all tying on now().
    op.add_column(
        "notes",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute("UPDATE notes SET updated_at = created_at")


def downgrade() -> None:
    op.drop_column("notes", "updated_at")
