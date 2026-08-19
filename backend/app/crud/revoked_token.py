from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core.security import decode_access_token
from ..db.models import RevokedToken


def revoke(db: Session, token: str, user_id: int) -> RevokedToken | None:
    """Record a token as signed out. None if it was not a token worth recording.

    Does not commit: logout has nothing else to do, but keeping the decision in
    the caller means this can join a larger transaction later without changing.

    Recording the same token twice is not an error. Signing out is something a
    client may retry, and the second attempt has already achieved its purpose.
    """
    claims = decode_access_token(token)
    if claims is None:
        # Unreadable, forged, or already expired. Nothing to revoke: it is
        # refused on its own merits every time it is presented.
        return None

    existing = db.scalars(select(RevokedToken).where(RevokedToken.jti == claims.jti)).first()
    if existing is not None:
        return existing

    row = RevokedToken(jti=claims.jti, user_id=user_id, expires_at=claims.expires_at)
    db.add(row)
    return row


def is_revoked(db: Session, jti: str) -> bool:
    """Whether this exact token has been signed out."""
    stmt = select(RevokedToken.id).where(RevokedToken.jti == jti)
    return db.scalars(stmt).first() is not None


def prune_expired(db: Session) -> int:
    """Drop records for tokens that have expired anyway; return how many went.

    Past its expiry a token is refused by the signature check whether or not it
    is listed here, so the row stops carrying information at that moment. Left
    alone the table only grows, one row per sign-out forever.
    """
    result = db.execute(
        delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc))
    )
    db.commit()
    return result.rowcount or 0
