"""
Password-reset links as the account page sees them.

The URL is in the read model for the same reason an invite code is in
`InviteRead`: the superuser asked for it in order to pass it on, and this
response is the only place it can ever be read. Unlike a code, it cannot be
re-read afterwards — only its hash is stored — so the page has to show it as
soon as it arrives.
"""

from typing import Annotated

from pydantic import BaseModel, Field

from .auth import Password
from .user import Email


class ResetLinkCreate(BaseModel):
    email: Email


class ResetLinkRead(BaseModel):
    # Echoed back as it is stored, so the issuer can see which account they just
    # opened — the request may have differed in case.
    email: str
    url: str
    expires_in_minutes: int


class ResetPasswordRequest(BaseModel):
    # The opaque token out of the link. Bounded so an absurd string is turned
    # away before it reaches the hash.
    token: Annotated[str, Field(min_length=1, max_length=256)]
    # The Password type here: this is a password about to be stored, so it is
    # held to the same floor and ceiling as one chosen at registration.
    password: Password
