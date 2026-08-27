"""
Invite codes as the account page sees them.

The code itself is in the read model on purpose. It is not a credential the
server needs to keep back from the person who issued it: they created it in
order to pass it on, and the listing is the only place it can be read again
after the response that created it has gone. A code they cannot re-read is a
code they have to reissue.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .user import Email


class InviteCreate(BaseModel):
    email: Email


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    # Null on the codes the CLI issued, which are bound to no address.
    invited_email: str | None
    created_at: datetime
    used_at: datetime | None


class InviteAdminRead(InviteRead):
    """Every invite, with the people on either end.

    A separate model from `InviteRead` rather than optional fields on it, so
    the endpoint that may disclose who issued a code and the endpoint that may
    not are two different response models and not one branch.
    """

    issued_by_email: str | None
    used_by_email: str | None
