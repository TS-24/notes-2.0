import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..db.models import InviteCode


def create_invite_code(
    db: Session,
    code: str | None = None,
    invited_email: str | None = None,
    issued_by_user_id: int | None = None,
) -> InviteCode:
    """Issue a code. Generates an unguessable one unless given a specific value.

    The address is folded here rather than at the call sites, so the column only
    ever holds one form and redemption has one form to compare against.
    """
    row = InviteCode(
        code=code or secrets.token_urlsafe(16),
        invited_email=invited_email.lower() if invited_email else None,
        issued_by_user_id=issued_by_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_unused(db: Session, code: str) -> InviteCode | None:
    """The named code, only if it has not been spent."""
    stmt = select(InviteCode).where(InviteCode.code == code, InviteCode.used_at.is_(None))
    return db.scalars(stmt).first()


def mark_used(db: Session, invite: InviteCode, user_id: int) -> InviteCode:
    """Spend a code on behalf of the account it created.

    Does not commit: the caller redeems inside the same transaction as the
    insert of the user, so a failure part-way cannot leave a code spent on an
    account that was never created.
    """
    invite.used_at = datetime.now(timezone.utc)
    invite.used_by_user_id = user_id
    db.add(invite)
    return invite


def list_invite_codes(db: Session) -> list[InviteCode]:
    """Every code, newest first, for the CLI to print."""
    return list(db.scalars(select(InviteCode).order_by(InviteCode.id.desc())))


def list_for_issuer(db: Session, user_id: int) -> list[InviteCode]:
    """The codes one account handed out, newest first.

    Codes with no issuer — the CLI's — belong to nobody and appear in no
    account's listing, which is why this filters on equality rather than
    treating a null issuer as everyone's.
    """
    stmt = (
        select(InviteCode)
        .where(InviteCode.issued_by_user_id == user_id)
        .order_by(InviteCode.id.desc())
    )
    return list(db.scalars(stmt))


def list_all(db: Session) -> list[InviteCode]:
    """Every code with the people on either end of it, for the superuser view.

    Eager-loads both relationships: the caller reads an email off each end of
    every row, and lazy loading that is a query per row.
    """
    stmt = (
        select(InviteCode)
        .options(joinedload(InviteCode.issued_by), joinedload(InviteCode.used_by))
        .order_by(InviteCode.id.desc())
    )
    return list(db.scalars(stmt))
