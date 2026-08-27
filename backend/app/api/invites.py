"""
Issuing invite codes, and reading back the ones you issued.

Registration is invite-only, and until this existed a code could only be made
by running the CLI against the database. That is fine on a laptop and wrong on
a deployed box, where it means opening a shell on the machine holding everyone's
data in order to hand a friend a string.

So any signed-in user may issue one. There is no quota: the people with accounts
are the people already trusted to be here, and a cap that has to be raised by
hand is a support request waiting to happen. What limits the damage instead is
that a code names the address it is for and works for no other, so a code that
leaks or is forwarded cannot be spent by whoever ends up holding it.

Nothing is emailed. The code comes back to the issuer and stays readable in
their listing, and passing it on is their business. That keeps the app off the
end of a mail provider and, more to the point, means no signed-in user can make
this server send mail to an address of their choosing.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..crud import invite_code as crud_invite
from ..crud import user as crud_user
from ..db.database import get_db
from ..db.models import InviteCode, User
from ..schemas.invite import InviteAdminRead, InviteCreate, InviteRead
from .deps import get_current_superuser, get_current_user

router = APIRouter(prefix="/invites", tags=["invites"])


@router.post("", response_model=InviteRead, status_code=status.HTTP_201_CREATED)
def issue_invite(
    payload: InviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InviteCode:
    """Issue a single-use code bound to one email address."""
    if crud_user.get_user_by_email_folded(db, payload.email) is not None:
        # A code this address can never redeem is a dead end, and without this
        # the issuer only finds out when the person they sent it to tries it.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That email already has an account"
        )

    return crud_invite.create_invite_code(
        db, invited_email=payload.email, issued_by_user_id=current_user.id
    )


@router.get("", response_model=list[InviteRead])
def list_my_invites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[InviteCode]:
    """The codes this account issued, newest first."""
    return crud_invite.list_for_issuer(db, current_user.id)


@router.get("/all", response_model=list[InviteAdminRead])
def list_every_invite(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> list[InviteAdminRead]:
    """Every code in the system, with who issued it and who spent it."""
    return [
        InviteAdminRead(
            **InviteRead.model_validate(row).model_dump(),
            issued_by_email=row.issued_by.email if row.issued_by else None,
            used_by_email=row.used_by.email if row.used_by else None,
        )
        for row in crud_invite.list_all(db)
    ]
