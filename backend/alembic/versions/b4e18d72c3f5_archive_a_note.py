"""a note can be put away

Revision ID: b4e18d72c3f5
Revises: f3a90c5d61b7
Create Date: 2026-08-25

One nullable column, and nothing else.

No sweep and no rewriting of titles. Notes already holding the literal string
"Untitled" keep it: they are named notes as far as the app is concerned from
here on, so nothing of the reader's moves without them asking. Only notes
created after this hold "" and can be recognised as blank.

The column is the whole feature. `archived_at IS NULL` is the library and
`IS NOT NULL` is the archive — one list under two filters, which is what makes
the toggle in the grid a filter rather than a second page.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4e18d72c3f5"
down_revision: Union[str, Sequence[str], None] = "f3a90c5d61b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable with no server_default: null *is* the value for a note in the
    # library, so backfilling every existing row is exactly what should not
    # happen here.
    op.add_column(
        "notes",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Dropping the column un-archives everything, which is the honest rollback:
    # without somewhere to record it, nothing is put away.
    op.drop_column("notes", "archived_at")
