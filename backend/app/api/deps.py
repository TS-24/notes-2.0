"""Shared API dependencies."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..core.config import COOKIE_NAME
from ..core.security import decode_access_token
from ..crud import revoked_token as crud_revoked
from ..db.database import get_db
from ..db.models import User

UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def token_from_request(request: Request) -> str | None:
    """The credential on this request, header first.

    The header is checked before the cookie so a script can override a stale
    browser session by passing one explicitly, and so the frontend's requests
    are unambiguous. The cookie exists for /docs and curl, which have no way
    to set a header conveniently.
    """
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return request.cookies.get(COOKIE_NAME)


def get_current_user_optional(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    """The requesting user, or None when there is no usable credential.

    Nothing uses this yet. It exists because the difference between "no user"
    and "bad credential" is a real one for any future route that is readable
    while signed out, and the place to draw that line is here rather than in
    each handler.
    """
    token = token_from_request(request)
    if token is None:
        return None

    claims = decode_access_token(token)
    if claims is None:
        return None

    # Signed and unexpired is not the same as still valid: signing out records
    # the token's id, and this is where that record is honoured. One indexed
    # lookup per request is the price of logout meaning anything.
    if crud_revoked.is_revoked(db, claims.jti):
        return None

    # Nor is it proof the account survived. Deleting a user does not reach the
    # tokens already issued for them, so this lookup is the only thing standing
    # between a deleted account and a working session.
    return db.get(User, claims.user_id)


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    """The user that owns the current request, or a 401.

    Every failure looks the same from outside: absent, malformed, expired, and
    naming-a-deleted-user all give the same 401. Distinguishing them would say
    which half of a forgery to work on next.
    """
    if user is None:
        raise UNAUTHENTICATED
    return user


def get_current_superuser(user: User = Depends(get_current_user)) -> User:
    """The user that owns the current request, if they are the superuser.

    Layered on `get_current_user` so an anonymous caller still gets a 401 and
    only a signed-in one gets the 403: the distinction is worth making here,
    because "sign in" and "you may not" are different things for the reader to
    do about it, and neither reveals anything a signed-in user cannot already
    work out about their own account.

    There is one flag and no role table. If this ever gates more than the two
    listings it was written for, that is the point to reach for something with
    named permissions rather than adding a second boolean.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted"
        )
    return user
