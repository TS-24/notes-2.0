"""keys per provider, and an active model on the account

Revision ID: a9d3c17b52f4
Revises: f2b6c48e0d19
Create Date: 2026-08-20

`provider_credentials` held one row per user, because the settings form asked
"which provider do you use" and answered it by replacing the row. That made
changing model cost the key: the two were saved together. They come apart here.

A key becomes one row per provider per user, and gains the catalogue that key
could reach when it was last checked — the list the model picker is built from,
and the evidence the credential works at all. Which provider and model the
account is *using* moves to two columns on `users`, because that is one fact
about the account rather than one per key, and one fact stored once cannot
disagree with itself.

Existing rows keep working: the credential each account had becomes the one it
is using, and its `model` becomes `active_model`. Where that column was null it
meant "the registry's default", so the defaults as they stood on this date are
written in below — a migration records what was true when it ran, and reading
the current registry here would make old databases upgrade differently
depending on when they got round to it.

The downgrade is real rather than a stub, because CI round-trips
upgrade -> downgrade -> upgrade and it is the only place a migration runs at all
(the test suite builds its schema with create_all).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9d3c17b52f4"
down_revision: Union[str, Sequence[str], None] = "f2b6c48e0d19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# app/services/llm.py's defaults on the date above, frozen. See the note in the
# docstring: this is history, not configuration.
DEFAULTS_AS_OF_THIS_MIGRATION = {
    "anthropic": "claude-opus-5",
    "openai": "gpt-5.1",
}


def upgrade() -> None:
    op.add_column("users", sa.Column("active_provider", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("active_model", sa.String(length=128), nullable=True))

    # Before the old columns go: the credential each account holds is the one it
    # is now using, and null there meant the registry's default.
    op.execute(
        sa.text(
            """
            UPDATE users SET
                active_provider = (
                    SELECT provider FROM provider_credentials
                    WHERE provider_credentials.user_id = users.id
                ),
                active_model = (
                    SELECT COALESCE(model, CASE provider
                        {cases}
                    END)
                    FROM provider_credentials
                    WHERE provider_credentials.user_id = users.id
                )
            """.format(
                cases="\n".join(
                    f"WHEN '{name}' THEN '{model}'"
                    for name, model in DEFAULTS_AS_OF_THIS_MIGRATION.items()
                )
            )
        )
    )

    op.add_column("provider_credentials", sa.Column("models", sa.JSON(), nullable=True))
    op.add_column(
        "provider_credentials",
        sa.Column("models_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )

    # The index stops being unique — a second provider is a second row now — and
    # the pair takes over the job of refusing two keys for the same one.
    op.drop_index(op.f("ix_provider_credentials_user_id"), table_name="provider_credentials")
    op.create_index(
        op.f("ix_provider_credentials_user_id"),
        "provider_credentials",
        ["user_id"],
        unique=False,
    )
    # Batch, because SQLite rewrites the table to add a constraint or drop a
    # column and this project's desktop build is SQLite. On Postgres it is the
    # plain ALTER it looks like.
    with op.batch_alter_table("provider_credentials") as batch:
        batch.create_unique_constraint("uq_credential_provider", ["user_id", "provider"])
        batch.drop_column("model")


def downgrade() -> None:
    with op.batch_alter_table("provider_credentials") as batch:
        batch.add_column(sa.Column("model", sa.String(length=128), nullable=True))
        batch.drop_constraint("uq_credential_provider", type_="unique")

    # The selection goes back onto the row it came from. A provider that is not
    # the active one keeps a null model, which is what that column meant before:
    # the registry's default.
    op.execute(
        sa.text(
            """
            UPDATE provider_credentials SET model = (
                SELECT active_model FROM users
                WHERE users.id = provider_credentials.user_id
                  AND users.active_provider = provider_credentials.provider
            )
            """
        )
    )

    # One row per user again, so the extra keys have to go. Going back loses
    # something either way; the oldest row is the one the account had before
    # this migration ran, which makes the round trip a no-op for anyone who
    # never added a second provider.
    op.execute(
        sa.text(
            """
            DELETE FROM provider_credentials
            WHERE id NOT IN (SELECT MIN(id) FROM provider_credentials GROUP BY user_id)
            """
        )
    )

    op.drop_index(op.f("ix_provider_credentials_user_id"), table_name="provider_credentials")
    op.create_index(
        op.f("ix_provider_credentials_user_id"),
        "provider_credentials",
        ["user_id"],
        unique=True,
    )
    with op.batch_alter_table("provider_credentials") as batch:
        batch.drop_column("models_fetched_at")
        batch.drop_column("models")

    op.drop_column("users", "active_model")
    op.drop_column("users", "active_provider")
