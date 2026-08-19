"""Add word_ladders

Caches the output of app/services/vocab.py. Building a ladder means walking
WordNet and scoring every candidate, and the answer never changes for a given
word — so compute it once for everybody rather than once per chevron click.

Keyed on the surface form rather than the lemma: rungs are inflected to match
the word that was asked about, so "run" and "running" are separate rows on
purpose. `pos` is the part of speech the ladder resolved to, not part of the key.

Revision ID: a7f3c02e5b18
Revises: b1d4e7a90c25
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7f3c02e5b18"
down_revision: Union[str, Sequence[str], None] = "b1d4e7a90c25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "word_ladders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("word", sa.String(length=255), nullable=False),
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
    )
    op.create_index(op.f("ix_word_ladders_word"), "word_ladders", ["word"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_word_ladders_word"), table_name="word_ladders")
    op.drop_table("word_ladders")
