"""Drop word_ladders

The word ladder is gone — service, ranker, cache and endpoint — so the table
that cached its output has nothing left to cache.

Safe to drop rather than keep: it held no user data and nothing referenced it.
Every row was derivable from WordNet plus the word, which is why it existed at
all (walking WordNet and scoring every candidate gives the same answer every
time, so it was worth computing once for everybody).

`downgrade` recreates the table as `c3e91b7d4406` left it — the original
columns plus `context_hash`, and the composite unique constraint rather than
the unique index on `word` alone. It comes back empty, which is the same state
a rebuilt cache starts in.

Revision ID: b6f4d1e83a07
Revises: c7a2f419e8d6
Create Date: 2026-08-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b6f4d1e83a07"
down_revision: Union[str, Sequence[str], None] = "c7a2f419e8d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The unique constraint and the index go with the table.
    op.drop_index(op.f("ix_word_ladders_word"), table_name="word_ladders")
    op.drop_table("word_ladders")


def downgrade() -> None:
    op.create_table(
        "word_ladders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column("context_hash", sa.String(length=64), server_default="", nullable=False),
        sa.Column("pos", sa.String(length=2), server_default="", nullable=False),
        sa.Column("rungs", sa.JSON(), nullable=False),
        sa.Column("origin_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("word", "context_hash", name="uq_word_ladders_word_context"),
    )
    op.create_index(op.f("ix_word_ladders_word"), "word_ladders", ["word"])
