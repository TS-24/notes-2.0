"""a note for every conversation that has none

Revision ID: f3a90c5d61b7
Revises: e7d41a20c9b8
Create Date: 2026-08-22

`e7d41a20c9b8` bound conversations to notes going forward and deliberately did
not backfill, on the grounds that the old ones kept their own card in the
library and lost nothing.

They do not any more. The library is a list of notes now, and a conversation is
reached by opening the note it belongs to — so a chat with no note is a chat
with no way in. This gives every one of them a note, which is the only thing
that keeps them reachable.

Nothing is invented. The title is the chat's own, and the body is its own
summary if it was ever finished, rendered the way the app renders it. A chat
that was never finished gets an empty note, because an empty note is the honest
description of a conversation that never came to anything yet.

Guarded by `note_id IS NULL`, so running it twice is a no-op. The downgrade
therefore does nothing at all, and that is deliberate twice over: a schema
rollback is not a reason to delete something the reader can now see and may
already have edited, and leaving them is exactly what lets the
upgrade -> downgrade -> upgrade round trip CI runs come out unchanged.
"""

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a90c5d61b7"
down_revision: Union[str, Sequence[str], None] = "e7d41a20c9b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# A snapshot of app/services/conversation_summary.py::NOTE_SECTIONS, copied
# rather than imported. A migration is pinned to the schema it was written
# against; importing app code would let it quietly mean something different the
# next time these headings are edited, and this one has already run by then.
SECTIONS = (
    ("What this was about", "summary_general"),
    ("What you were asking", "summary_questions"),
    ("What the answers covered", "summary_answers"),
)

UNTITLED = "Untitled"

# Only the columns this migration reads and writes. Reflecting the real tables
# would couple it to whatever they look like now rather than to what they looked
# like here.
chats = sa.table(
    "chats",
    sa.column("id", sa.Integer),
    sa.column("user_id", sa.Integer),
    sa.column("title", sa.String),
    sa.column("note_id", sa.Integer),
    sa.column("summarized_at", sa.DateTime(timezone=True)),
    sa.column("summary_general", sa.Text),
    sa.column("summary_topics", sa.JSON),
    sa.column("summary_questions", sa.Text),
    sa.column("summary_answers", sa.Text),
)

notes = sa.table(
    "notes",
    sa.column("id", sa.Integer),
    sa.column("user_id", sa.Integer),
    sa.column("title", sa.String),
    sa.column("content", sa.Text),
    sa.column("is_pinned", sa.Boolean),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def _as_note(row) -> str:
    """The chat's summary as the text of a note, or nothing if it has none."""
    if row.summarized_at is None:
        return ""

    parts = [
        f"{heading}\n\n{getattr(row, field) or ''}" for heading, field in SECTIONS
    ]
    topics = row.summary_topics or []
    if topics:
        parts.append("Topics\n\n" + ", ".join(topics))
    return "\n\n".join(parts)


def upgrade() -> None:
    bind = op.get_bind()
    orphaned = bind.execute(
        sa.select(
            chats.c.id,
            chats.c.user_id,
            chats.c.title,
            chats.c.summarized_at,
            chats.c.summary_general,
            chats.c.summary_topics,
            chats.c.summary_questions,
            chats.c.summary_answers,
        ).where(chats.c.note_id.is_(None))
    ).fetchall()

    now = datetime.now(timezone.utc)
    for row in orphaned:
        # Row at a time, and the id read back before the next one: a bulk insert
        # gives no portable way to pair each new note with the chat it was made
        # for, and there are only ever as many of these as the account had
        # conversations before the binding existed.
        note_id = bind.execute(
            sa.insert(notes)
            .values(
                user_id=row.user_id,
                title=row.title or UNTITLED,
                content=_as_note(row),
                is_pinned=False,
                created_at=now,
                updated_at=now,
            )
            .returning(notes.c.id)
        ).scalar_one()

        bind.execute(
            sa.update(chats).where(chats.c.id == row.id).values(note_id=note_id)
        )


def downgrade() -> None:
    """Deliberately nothing. See the note at the top of this file."""
