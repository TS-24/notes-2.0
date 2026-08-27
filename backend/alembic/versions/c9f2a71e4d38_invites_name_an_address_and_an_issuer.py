"""Invites name an address and an issuer, and one account is a superuser

Invites used to come only from the CLI, so a code was an anonymous string that
worked for whoever held it. Issuing one from the account page changes what a
code has to record: who handed it out, and which address it is for.

Both new columns on `invite_codes` are nullable, and null means the same thing
in each — the CLI made this one. Every code outstanding when this runs is in
exactly that state, which is why neither column can be NOT NULL: making them so
would mean inventing an issuer and an address for codes that have neither, and
the honest value is the one that says nobody.

A null `invited_email` also stays *functional* rather than merely tolerated:
`api/auth.py` treats it as an unbound code that anyone may spend, which is what
every existing code already is. Nothing outstanding is invalidated by this.

`users.is_superuser` arrives with a false default, so every existing account is
unchanged, and is then set on the lowest id. That is the account that registered
first, and on this deployment it is the owner's. Doing it here rather than
leaving every row false matters: the flag gates the only view of who is on the
system, and a database where nobody holds it can only be fixed from a psql
shell. New databases do not need this — `crud/user.py` gives the flag to the
first account created — but a database that already has users has no first
account left to create.

Revision ID: c9f2a71e4d38
Revises: a4c8e2f70b13
Create Date: 2026-08-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9f2a71e4d38"
down_revision: Union[str, Sequence[str], None] = "a4c8e2f70b13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Named rather than left to the dialect, so `downgrade` has something to drop.
# The unnamed foreign key already on `used_by_user_id` is why: it cannot be
# dropped by name, and this migration should not repeat that.
ISSUER_FK = "fk_invite_codes_issued_by_user_id_users"


def upgrade() -> None:
    op.add_column("invite_codes", sa.Column("invited_email", sa.String(255), nullable=True))
    op.add_column("invite_codes", sa.Column("issued_by_user_id", sa.Integer(), nullable=True))
    # Batch because SQLite cannot add a constraint to an existing table. On
    # Postgres, where this actually runs, it is a plain ALTER either way.
    with op.batch_alter_table("invite_codes") as batch:
        batch.create_foreign_key(ISSUER_FK, "users", ["issued_by_user_id"], ["id"])

    op.add_column(
        "users",
        sa.Column(
            "is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    # The first account registered, which is the owner's. A no-op on an empty
    # database, where the first account created will get the flag on its own.
    op.execute(
        "UPDATE users SET is_superuser = true WHERE id = (SELECT MIN(id) FROM users)"
    )


def downgrade() -> None:
    op.drop_column("users", "is_superuser")

    with op.batch_alter_table("invite_codes") as batch:
        batch.drop_constraint(ISSUER_FK, type_="foreignkey")
    op.drop_column("invite_codes", "issued_by_user_id")
    # Losing which address a code was for makes every outstanding code unbound
    # again, which is the behaviour the schema below it has. Nothing is stranded.
    op.drop_column("invite_codes", "invited_email")
