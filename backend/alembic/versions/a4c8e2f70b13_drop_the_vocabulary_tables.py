"""Drop the vocabulary tables

The vocabulary analysis is gone — the service, its endpoint, the known-words
list, the word-definition CRUD and the whole `/analytics` page — so the three
tables behind it have nothing left to hold.

Every one of them was empty when this was written: `word_definitions` 0 rows,
`known_words` 0 rows, `note_word` 0 rows, counted against the live database. So
this drops no data, and `downgrade` restoring them empty restores the true
state rather than an approximation of it.

Order matters on the way down and on the way up. `note_word` references both
`notes` and `word_definitions`, so it is dropped first and created last, or the
foreign keys refuse.

Revision ID: a4c8e2f70b13
Revises: b6f4d1e83a07
Create Date: 2026-08-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4c8e2f70b13"
down_revision: Union[str, Sequence[str], None] = "b6f4d1e83a07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("note_word")
    op.drop_table("word_definitions")
    op.drop_index(op.f("ix_known_words_user_id"), table_name="known_words")
    op.drop_table("known_words")


def downgrade() -> None:
    op.create_table(
        "known_words",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "word", name="uq_known_words_user_word"),
    )
    op.create_index(
        op.f("ix_known_words_user_id"), "known_words", ["user_id"], unique=False
    )
    op.create_table(
        "word_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "note_word",
        sa.Column("note_id", sa.Integer(), nullable=False),
        sa.Column("word_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["note_id"], ["notes.id"]),
        sa.ForeignKeyConstraint(["word_id"], ["word_definitions.id"]),
        sa.PrimaryKeyConstraint("note_id", "word_id"),
    )
