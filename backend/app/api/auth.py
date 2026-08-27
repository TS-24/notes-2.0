from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import ACCESS_TOKEN_TTL, COOKIE_NAME, COOKIE_SECURE
from ..core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from ..crud import invite_code as crud_invite
from ..crud import revoked_token as crud_revoked
from ..crud import user as crud_user
from ..db.database import get_db
from ..schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from .deps import token_from_request

router = APIRouter(prefix="/auth", tags=["auth"])

# One message for a code that never existed and a code already spent. Saying
# which would turn the endpoint into a way to test codes.
INVALID_INVITE = "That invite code is not valid"
INVALID_CREDENTIALS = "Incorrect email or password"

# Verified against when the email is unknown, so a login attempt costs the same
# whether or not the account exists. Without this the response time alone says
# which emails are registered.
_DUMMY_HASH = hash_password("a password nobody has, hashed once at import")


def _set_token_cookie(response: Response, token: str) -> None:
    """Attach the token as a cookie for callers that are not the SSR frontend.

    The React Router server reads the token out of the response body and keeps
    its own cookie on its own origin, because this one is set for the API's
    origin and the browser never talks to it directly. This cookie is what
    makes /docs and curl usable.
    """
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(ACCESS_TOKEN_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Create an account against a single-use invite code."""
    invite = crud_invite.get_unused(db, payload.invite_code)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_INVITE)

    # A code issued from an account page names the address it is for; one issued
    # from the CLI names nobody and still works for anyone. The refusal reuses
    # INVALID_INVITE for the same reason the two cases above share it: a reply
    # that said "wrong email for this code" would answer, for anyone holding a
    # code, which address it was meant for.
    if invite.invited_email is not None and invite.invited_email != payload.email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_INVITE)

    if crud_user.get_user_by_email(db, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    try:
        user = crud_user.create_user(
            db,
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
    except IntegrityError:
        # Lost a race against another registration on the same email. The code
        # is still unspent, which is the outcome we want.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    crud_invite.mark_used(db, invite, user.id)
    db.commit()

    token = create_access_token(user.id)
    _set_token_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Exchange an email and password for an access token."""
    user = crud_user.get_user_by_email(db, payload.email)

    # Hash even when there is no user, so the two paths cost the same.
    password_hash = user.password_hash if user is not None else _DUMMY_HASH
    if not verify_password(password_hash, payload.password) or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.id)
    _set_token_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    """End this session, for real.

    The token's id is recorded so it is refused from here on. That is the part
    that matters: clearing the cookie only stops this browser sending it, and
    does nothing about a copy taken somewhere else.

    Only this token. Other sessions for the same account keep working, because
    signing out of one browser is not a request to sign out of all of them.

    Deliberately not authenticated. Someone holding a token they cannot use is
    still entitled to retire it, and a 401 here would leave a session alive
    that the caller was trying to end.
    """
    token = token_from_request(request)
    if token is not None:
        claims = decode_access_token(token)
        if claims is not None:
            crud_revoked.revoke(db, token, claims.user_id)
            db.commit()

    # The attributes have to match the ones it was set with, or the browser
    # keeps the original cookie and logging out silently does nothing.
    response.delete_cookie(
        COOKIE_NAME, path="/", httponly=True, samesite="lax", secure=COOKIE_SECURE
    )
