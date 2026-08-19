from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import COOKIE_NAME, COOKIE_SECURE
from ..crud import user as crud_user
from ..db.database import get_db
from ..db.models import User
from ..schemas.user import UserRead, UserUpdate
from .deps import get_current_user

# Every route here is about the signed-in account, so none of them takes an id.
#
# There used to be four that did, and none compared the id to the caller: any
# account could read, rename or delete any other. There were also two without
# any caller left — a listing of every registered email, and an unauthenticated
# POST that created accounts beside the invite-only registration it ignored.
# Both are gone rather than guarded, because a route that should never be
# reachable is better deleted than defended.
router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def get_current_user_route(current_user: User = Depends(get_current_user)) -> UserRead:
    """The signed-in user."""
    return current_user


@router.patch("/me", response_model=UserRead)
def update_current_user(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    try:
        user = crud_user.update_user(
            db, current_user.id, **payload.model_dump(exclude_unset=True)
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    assert user is not None  # the token already proved this row exists
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete the signed-in account, its notes and its known words.

    The cookie goes with it. The token stays technically valid until it
    expires, but it now names a user that no longer exists, which resolves to
    a 401 like any other bad credential.
    """
    crud_user.delete_user(db, current_user.id)
    response.delete_cookie(
        COOKIE_NAME, path="/", httponly=True, samesite="lax", secure=COOKIE_SECURE
    )
