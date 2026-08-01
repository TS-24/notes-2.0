"""Key word ladders by context as well as word

The contextual engine (app/services/lexsub.py) masks a word inside its sentence
and asks a language model what fits, so its answer is a function of the sentence
rather than of the word. The old unique index on `word` alone cannot express
that: two sentences containing "model" have two different ladders.

`context_hash` is empty for the WordNet engine, which never sees a sentence, so
its rows keep behaving exactly as before.

Revision ID: c3e91b7d4406
Revises: a7f3c02e5b18
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3e91b7d4406"
down_revision: Union[str, Sequence[str], None] = "a7f3c02e5b18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "word_ladders",
        sa.Column("context_hash", sa.String(length=64), server_default="", nullable=False),
    )
    # The word alone is no longer unique; the pair is.
    op.drop_index(op.f("ix_word_ladders_word"), table_name="word_ladders")
    op.create_index(op.f("ix_word_ladders_word"), "word_ladders", ["word"])
    op.create_unique_constraint(
        "uq_word_ladders_word_context", "word_ladders", ["word", "context_hash"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_word_ladders_word_context", "word_ladders", type_="unique")
    # Going back to a unique word means dropping every contextual row, since
    # several of them can share one word.
    op.execute("DELETE FROM word_ladders WHERE context_hash <> ''")
    op.drop_column("word_ladders", "context_hash")
    op.drop_index(op.f("ix_word_ladders_word"), table_name="word_ladders")
    op.create_index(op.f("ix_word_ladders_word"), "word_ladders", ["word"], unique=True)
