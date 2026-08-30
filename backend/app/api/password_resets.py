"""
Issuing a password-reset link.

The sibling of `api/invites.py`, and built on the same decision: nothing is
emailed. The link comes back to whoever asked for it and they pass it on, which
keeps this app off the end of a mail provider and — the part that matters —
means nobody can make this server send mail to an address of their choosing.

Two things differ from an invite, and both follow from what a reset link is
worth. An invite code creates a *new* account bound to one address, so any
signed-in user may issue one. A reset link opens an account that already exists,
which is a handover of somebody's notes, so only the superuser may issue one.
And an invite code can be read back from its listing forever, while this is
shown exactly once: only the hash of it is stored, so there is nothing to list.
Losing it costs one more click.

Like `invites.py`, this takes the address in the body rather than an id in the
path — see the note at the top of `api/users.py` about routes that read an id
out of the path to decide whose data they act on.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.config import FRONTEND_ORIGIN, RESET_TOKEN_TTL
from ..core.security import hash_reset_token, new_reset_token
from ..crud import password_reset as crud_reset
from ..crud import user as crud_user
from ..db.database import get_db
from ..db.models import User
from ..schemas.password_reset import ResetLinkCreate, ResetLinkRead
from .deps import get_current_superuser

router = APIRouter(prefix="/password-resets", tags=["password-resets"])


@router.post("", response_model=ResetLinkRead, status_code=status.HTTP_201_CREATED)
def issue_reset_link(
    payload: ResetLinkCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> ResetLinkRead:
    """Mint a one-time reset link for an existing account.

    Says plainly when the address has no account. That is not the leak it would
    be on a public endpoint — the caller is the superuser, who can already read
    the whole user list — and the alternative is handing them a link that
    silently belongs to nobody.
    """
    user = crud_user.get_user_by_email_folded(db, payload.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No account for that email"
        )

    # One live link per account: issuing a new one retires any earlier link, so
    # a link handed to the wrong person can be cancelled by reissuing.
    crud_reset.invalidate_for_user(db, user.id)
    raw_token = new_reset_token()
    crud_reset.create(
        db,
        user.id,
        hash_reset_token(raw_token),
        datetime.now(timezone.utc) + RESET_TOKEN_TTL,
    )
    db.commit()

    return ResetLinkRead(
        email=user.email,
        url=f"{FRONTEND_ORIGIN}/reset-password?token={raw_token}",
        expires_in_minutes=int(RESET_TOKEN_TTL.total_seconds() // 60),
    )
