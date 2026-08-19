import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import InviteCode


def create_invite_code(db: Session, code: str | None = None) -> InviteCode:
    """Issue a code. Generates an unguessable one unless given a specific value."""
    row = InviteCode(code=code or secrets.token_urlsafe(16))
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
