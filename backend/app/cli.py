"""
Administrative commands, run as `python -m app.cli <command>`.

Registration is invite-only, so this is how the first account comes into being.
It talks to the database directly rather than to the API, because it has to work
before any account exists to authenticate as.

Invites no longer have to come from here: any signed-in user can issue one from
their account page, and those are bound to the address they were issued for. The
command below still issues an unbound one, which is what you want for the first
account, when there is nobody to attribute it to and no form to reach.
"""

import argparse
import sys
from datetime import datetime, timezone
from getpass import getpass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .core.config import FRONTEND_ORIGIN, RESET_TOKEN_TTL
from .core.security import hash_password, hash_reset_token, new_reset_token
from .crud import invite_code as crud_invite
from .crud import password_reset as crud_reset
from .crud import revoked_token as crud_revoked
from .crud import user as crud_user
from .db.database import SessionLocal
from .db.models import Note, User

DEV_USER_EMAIL = "dev@example.com"


def issue_invite(db: Session, args: argparse.Namespace) -> int:
    invite = crud_invite.create_invite_code(db, invited_email=args.email)
    print(invite.code)
    return 0


def list_invites(db: Session, args: argparse.Namespace) -> int:
    rows = crud_invite.list_invite_codes(db)
    if not rows:
        print("No invite codes issued.")
        return 0
    for row in rows:
        state = f"used {row.used_at:%Y-%m-%d}" if row.used_at else "unused"
        # A code bound to nobody works for anyone, which is the thing worth
        # seeing at a glance in a list of outstanding codes.
        print(f"{row.code}\t{state}\t{row.invited_email or 'anyone'}")
    return 0


def promote_user(db: Session, args: argparse.Namespace) -> int:
    """Grant the superuser flag to an existing account.

    Not the ordinary path: the first account created gets the flag on its own.
    This is the way back if that account is deleted, which would otherwise leave
    a database with nobody able to read the admin listings and no way to appoint
    anyone short of a psql shell.
    """
    user = crud_user.get_user_by_email(db, args.email)
    if user is None:
        print(f"No account for {args.email}.", file=sys.stderr)
        return 1

    if user.is_superuser:
        print(f"{args.email} is already a superuser.")
        return 0

    user.is_superuser = True
    db.commit()
    print(f"{args.email} is now a superuser.")
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

    db.delete(dev)
    db.commit()

    print(f"Moved {notes} note(s) to {heir.email}, removed the dev user.")
    return 0


def prune_tokens(db: Session, args: argparse.Namespace) -> int:
    """Drop revocation records for tokens that have expired anyway.

    Signing out writes a row and nothing removes it, so the table grows by one
    per sign-out forever. Past its expiry a token is refused whether or not it
    is listed, which is the moment its row stops meaning anything.
    """
    removed = crud_revoked.prune_expired(db)
    resets = crud_reset.prune_expired(db)
    print(
        f"Removed {removed} expired revocation record(s) and "
        f"{resets} expired reset link(s)."
    )
    return 0


def issue_reset(db: Session, args: argparse.Namespace) -> int:
    """Print a one-time password-reset link for an account.

    The account page does this too, and does it better — no shell on the box.
    This exists for the one case that page cannot serve: the superuser is the
    account locked out, so there is nobody left signed in to issue the link.

    The URL alone goes to stdout so `... | pbcopy` grabs just that; the expiry
    note goes to stderr.
    """
    user = crud_user.get_user_by_email_folded(db, args.email)
    if user is None:
        print(f"No account for {args.email}.", file=sys.stderr)
        return 1

    # One live link per account: retire any earlier one first.
    crud_reset.invalidate_for_user(db, user.id)
    raw_token = new_reset_token()
    crud_reset.create(
        db,
        user.id,
        hash_reset_token(raw_token),
        datetime.now(timezone.utc) + RESET_TOKEN_TTL,
    )
    db.commit()

    minutes = int(RESET_TOKEN_TTL.total_seconds() // 60)
    print(f"{FRONTEND_ORIGIN}/reset-password?token={raw_token}")
    print(f"Valid once, for {minutes} minutes.", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    invite = commands.add_parser("issue-invite", help="Issue a single-use invite code")
    invite.add_argument(
        "--email",
        help="Bind the code to this address. Without it the code works for anyone.",
    )
    invite.set_defaults(func=issue_invite)
    commands.add_parser("list-invites", help="Show every invite code").set_defaults(
        func=list_invites
    )

    new_user = commands.add_parser("create-user", help="Create an account")
    new_user.add_argument("--email", required=True)
    new_user.add_argument("--username", help="Defaults to the part before the @")
    new_user.set_defaults(func=create_user)

    promote = commands.add_parser(
        "promote", help="Make an existing account a superuser"
    )
    promote.add_argument("--email", required=True)
    promote.set_defaults(func=promote_user)

    commands.add_parser(
        "prune-tokens", help="Forget revoked tokens that have expired anyway"
    ).set_defaults(func=prune_tokens)

    reset = commands.add_parser(
        "issue-reset",
        help="Print a one-time password-reset link, when nobody is left to issue one",
    )
    reset.add_argument("--email", required=True, help="The account to reset")
    reset.set_defaults(func=issue_reset)

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
