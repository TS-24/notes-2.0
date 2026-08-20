"""add chats and provider credentials

Revision ID: f2b6c48e0d19
Revises: b7c31d9f04ae
Create Date: 2026-08-19

Three tables for AI chats: the credential the reader supplies, the conversation,
and its turns. The summary lives on `chats` as four nullable columns written
together — see app/crud/chat.py::store_summary, which is the only thing that
writes them and writes all four at once.

The downgrade is real rather than a stub, because CI round-trips
upgrade -> downgrade -> upgrade and it is the only place a migration runs at all
(the test suite builds its schema with create_all).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2b6c48e0d19"
down_revision: Union[str, Sequence[str], None] = "b7c31d9f04ae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        # Fernet ciphertext, never the key itself — app/core/secrets.py. Text
        # rather than String(n): the length follows the provider's key format,
        # which is not ours to bound.
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # Unique *index* rather than a constraint plus an index: one row per user is
    # the rule, and this is the shape `unique=True, index=True` produces on the
    # model, so the two stay comparable.
    op.create_index(
        op.f("ix_provider_credentials_user_id"),
        "provider_credentials",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "chats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # The three parts of the summary. Null until the conversation is
        # finished; `summarized_at` being set is what "finished" means.
        sa.Column("summary_general", sa.Text(), nullable=True),
        sa.Column("summary_topics", sa.JSON(), nullable=True),
        sa.Column("summary_questions", sa.Text(), nullable=True),
        sa.Column("summary_answers", sa.Text(), nullable=True),
        sa.Column("summarized_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chats_user_id"), "chats", ["user_id"], unique=False)

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_messages_chat_id"), "chat_messages", ["chat_id"], unique=False
    )


def downgrade() -> None:
    # Reverse order: chat_messages points at chats, which points at users.
    op.drop_index(op.f("ix_chat_messages_chat_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index(op.f("ix_chats_user_id"), table_name="chats")
    op.drop_table("chats")
    op.drop_index(
        op.f("ix_provider_credentials_user_id"), table_name="provider_credentials"
    )
    op.drop_table("provider_credentials")
