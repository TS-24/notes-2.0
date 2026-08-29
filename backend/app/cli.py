"""
Administrative commands, run as `python -m app.cli <command>`.

Registration is invite-only and there is no admin role, so this is how the
first account and every invite come into being. It talks to the database
directly rather than to the API, because it has to work before any account
exists to authenticate as.
"""

import argparse
import sys
from datetime import datetime, timezone
from getpass import getpass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .core.security import hash_password
from .crud import invite_code as crud_invite
from .crud import password_reset as crud_reset
from .crud import revoked_token as crud_revoked
from .crud import user as crud_user
from .db.database import SessionLocal
from .db.models import KnownWord, Note, User

DEV_USER_EMAIL = "dev@example.com"


def issue_invite(db: Session, args: argparse.Namespace) -> int:
    invite = crud_invite.create_invite_code(db)
    print(invite.code)
    return 0


def list_invites(db: Session, args: argparse.Namespace) -> int:
    rows = crud_invite.list_invite_codes(db)
    if not rows:
        print("No invite codes issued.")
        return 0
    for row in rows:
        state = f"used {row.used_at:%Y-%m-%d}" if row.used_at else "unused"
        print(f"{row.code}\t{state}")
    return 0


def create_user(db: Session, args: argparse.Namespace) -> int:
    """Create an account without an invite.

    The CLI is already the privileged path — anyone running it has the
    database — so requiring a code here would be ceremony rather than a
    control. Invites gate the public endpoint, not this.
    """
    if crud_user.get_user_by_email(db, args.email) is not None:
        print(f"{args.email} already has an account.", file=sys.stderr)
        return 1

    # Read rather than take as a flag, so it stays out of shell history and
    # the process list.
    password = getpass("Password: ")
    if len(password) < 12:
        print("Password must be at least 12 characters.", file=sys.stderr)
        return 1
    if password != getpass("Repeat: "):
        print("Passwords did not match.", file=sys.stderr)
        return 1

    user = crud_user.create_user(
        db,
        username=args.username or args.email.split("@")[0],
        email=args.email,
        password_hash=hash_password(password),
    )
    print(f"Created user {user.id} ({user.email}).")
    return 0


def adopt_dev_data(db: Session, args: argparse.Namespace) -> int:
    """Move the seeded dev user's rows to a real account, then remove it.

    Not a migration: a migration cannot know which account should inherit, and
    the answer only exists once someone has registered.
    """
    dev = crud_user.get_user_by_email(db, DEV_USER_EMAIL)
    if dev is None:
        print("No dev user to adopt from.")
        return 0

    heir = crud_user.get_user_by_email(db, args.email)
    if heir is None:
        print(f"No account for {args.email}. Create it first.", file=sys.stderr)
        return 1
    if heir.id == dev.id:
        print("That is the dev user itself.", file=sys.stderr)
        return 1

    notes = db.execute(
        update(Note).where(Note.user_id == dev.id).values(user_id=heir.id)
    ).rowcount

    # known_words is unique on (user_id, word), so a word both accounts already
    # know would collide on reassignment. The heir's own row is the one to
    # keep: dropping the duplicate is not a loss, both mean the same thing.
    already = set(db.scalars(select(KnownWord.word).where(KnownWord.user_id == heir.id)))
    duplicates = [
        row
        for row in db.scalars(select(KnownWord).where(KnownWord.user_id == dev.id))
        if row.word in already
    ]
    for row in duplicates:
        db.delete(row)
    db.flush()

    words = db.execute(
        update(KnownWord).where(KnownWord.user_id == dev.id).values(user_id=heir.id)
    ).rowcount

    db.delete(dev)
    db.commit()

    print(
        f"Moved {notes} note(s) and {words} known word(s) to {heir.email}, "
        f"dropped {len(duplicates)} duplicate(s), removed the dev user."
    )
    return 0


def prune_tokens(db: Session, args: argparse.Namespace) -> int:
    """Drop expired rows from revoked_tokens and password_reset_tokens.

    Both tables grow by one row per event — a sign-out, a reset request — and
    nothing else clears them. Past its expiry a revoked token is refused by the
    signature check regardless, and a reset link by get_valid_by_hash, so the
    row stops meaning anything at that moment.
    """
    revoked = crud_revoked.prune_expired(db)
    resets = crud_reset.prune_expired(db)
    print(
        f"Removed {revoked} expired revocation record(s) and "
        f"{resets} expired reset token(s)."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("issue-invite", help="Issue a single-use invite code").set_defaults(
        func=issue_invite
    )
    commands.add_parser("list-invites", help="Show every invite code").set_defaults(
        func=list_invites
    )

    new_user = commands.add_parser("create-user", help="Create an account")
    new_user.add_argument("--email", required=True)
    new_user.add_argument("--username", help="Defaults to the part before the @")
    new_user.set_defaults(func=create_user)

    commands.add_parser(
        "prune-tokens", help="Forget revoked tokens that have expired anyway"
    ).set_defaults(func=prune_tokens)

    adopt = commands.add_parser(
        "adopt-dev-data", help="Move the seeded dev user's notes to a real account"
    )
    adopt.add_argument("--email", required=True, help="The account that inherits")
    adopt.set_defaults(func=adopt_dev_data)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db = SessionLocal()
    try:
        return args.func(db, args)
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
