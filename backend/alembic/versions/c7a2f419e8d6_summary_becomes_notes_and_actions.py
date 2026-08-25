"""the summary becomes notes and actions

Revision ID: c7a2f419e8d6
Revises: b4e18d72c3f5
Create Date: 2026-08-25

Four columns down to two.

`summary_general`, `summary_topics`, `summary_questions` and `summary_answers`
forced every finished conversation into a shape two parts of which were about
the reader rather than the subject — "the main focus of the reader's questions"
— which is what invited a summary describing how somebody wrote instead of what
was established. Notes and actions replace them.

**No backfill, and nothing is lost by that.** The prose the reader keeps has
never lived in these columns: `conversation_summary.as_note` writes it into the
note the conversation is bound to, and the note is the durable half. Nothing in
the interface reads the summary columns at all — finishing a chat redirects to
its note. What is dropped here is a second copy that was already write-only.

The downgrade puts the four columns back, empty. It cannot reconstruct them, and
a rollback that invented content would be worse than one that admits the shape
changed. Both directions are pure DDL, so the round trip CI runs is clean.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7a2f419e8d6"
down_revision: Union[str, Sequence[str], None] = "b4e18d72c3f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chats", sa.Column("summary_notes", sa.Text(), nullable=True))
    op.add_column("chats", sa.Column("summary_actions", sa.JSON(), nullable=True))

    op.drop_column("chats", "summary_general")
    op.drop_column("chats", "summary_topics")
    op.drop_column("chats", "summary_questions")
    op.drop_column("chats", "summary_answers")


def downgrade() -> None:
    op.add_column("chats", sa.Column("summary_general", sa.Text(), nullable=True))
    op.add_column("chats", sa.Column("summary_topics", sa.JSON(), nullable=True))
    op.add_column("chats", sa.Column("summary_questions", sa.Text(), nullable=True))
    op.add_column("chats", sa.Column("summary_answers", sa.Text(), nullable=True))

    op.drop_column("chats", "summary_notes")
    op.drop_column("chats", "summary_actions")
