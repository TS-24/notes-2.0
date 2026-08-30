"""
Storage for single-use password-reset tokens.

Shaped like `crud/revoked_token.py`: the write helpers do not commit, so a
handler can group them into one transaction, and only `prune_expired` — which is
housekeeping with nothing else around it — commits on its own.

Only the SHA-256 of a token is ever passed in here. The token itself lives in
the emailed link and nowhere else; see `core/security.py::hash_reset_token`.
"""

from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..db.models import PasswordResetToken


def create(
    db: Session, user_id: int, token_hash: str, expires_at: datetime
) -> PasswordResetToken:
    """Record a freshly issued reset token. Does not commit."""
    row = PasswordResetToken(
        user_id=user_id, token_hash=token_hash, expires_at=expires_at
    )
    db.add(row)
    return row


def get_valid_by_hash(db: Session, token_hash: str) -> PasswordResetToken | None:
    """An unused, unexpired token with this hash, or None.

    "No such token", "already used" and "expired" all collapse to None, for the
    reason login gives one answer for a bad email and a bad password: the caller
    turns every one of them into the same 400, and separating them would tell an
    attacker which part to change.
    """
    stmt = select(PasswordResetToken).where(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > datetime.now(timezone.utc),
    )
    return db.scalars(stmt).first()


def mark_used(db: Session, row: PasswordResetToken) -> None:
    """Stamp a token as spent. Does not commit."""
    row.used_at = datetime.now(timezone.utc)


def invalidate_for_user(db: Session, user_id: int) -> int:
    """Spend every outstanding token for a user; return how many.

    Run when a link is issued and again when one is redeemed, so an account
    never has more than one live link. Does not commit.
    """
    result = db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=datetime.now(timezone.utc))
    )
    return result.rowcount or 0


def prune_expired(db: Session) -> int:
    """Drop tokens past their expiry; return how many went, and commit.

    Past `expires_at` a token is refused regardless, so the row stops meaning
    anything at that moment. Nothing else removes them, so the table would grow
    one row per request forever.
    """
    result = db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.expires_at < datetime.now(timezone.utc)
        )
    )
    db.commit()
    return result.rowcount or 0
