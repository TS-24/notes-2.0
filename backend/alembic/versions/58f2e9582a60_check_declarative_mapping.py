"""Check declarative mapping

Revision ID: 58f2e9582a60
Revises: c74ae4ac3d9f
Create Date: 2026-06-20 22:09:50.474327

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58f2e9582a60'
down_revision: Union[str, Sequence[str], None] = 'c74ae4ac3d9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # batch_alter_table rather than a bare alter_column: SQLite cannot ALTER a
    # column, and the desktop build runs these same migrations against SQLite.
    # On Postgres batch mode emits the plain ALTER, so this changes nothing
    # there — and nothing re-runs on a database that has already applied it.
    with op.batch_alter_table('notes') as batch:
        batch.alter_column('user_id', existing_type=sa.INTEGER(), nullable=False)
    with op.batch_alter_table('word_definitions') as batch:
        batch.alter_column('user_id', existing_type=sa.INTEGER(), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('word_definitions') as batch:
        batch.alter_column('user_id', existing_type=sa.INTEGER(), nullable=True)
    with op.batch_alter_table('notes') as batch:
        batch.alter_column('user_id', existing_type=sa.INTEGER(), nullable=True)
