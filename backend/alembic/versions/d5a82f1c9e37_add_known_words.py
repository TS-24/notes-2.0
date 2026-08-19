"""add known_words

Revision ID: d5a82f1c9e37
Revises: c3e91b7d4406
Create Date: 2026-08-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5a82f1c9e37"
down_revision: Union[str, Sequence[str], None] = "c3e91b7d4406"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "known_words",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "word", name="uq_known_words_user_word"),
    )
    op.create_index(
        op.f("ix_known_words_user_id"), "known_words", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_known_words_user_id"), table_name="known_words")
    op.drop_table("known_words")
