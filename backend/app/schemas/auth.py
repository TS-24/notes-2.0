from typing import Annotated

from pydantic import BaseModel, Field

from .user import Email, Username

# The floor is a length rather than a character-class rule: a long passphrase
# beats a short one with a symbol in it, and the rules only push people toward
# the same handful of predictable substitutions. The ceiling matters more than
# it looks — argon2 is deliberately expensive, so an unbounded password is a
# way to spend the server's CPU on request.
Password = Annotated[str, Field(min_length=12, max_length=128)]


class RegisterRequest(BaseModel):
    username: Username
    email: Email
    password: Password
    invite_code: Annotated[str, Field(min_length=1, max_length=64)]


class LoginRequest(BaseModel):
    email: Email
    # Not the Password type: the length rules belong on what may be stored, not
    # on what may be attempted. Applying them here would answer "that is not
    # even a possible password of ours" before checking anything.
    password: str


class ForgotPasswordRequest(BaseModel):
    email: Email


class ResetPasswordRequest(BaseModel):
    # The opaque token from the emailed link. Bounded so an absurd string is
    # turned away before it reaches the hash.
    token: Annotated[str, Field(min_length=1, max_length=256)]
    # The Password type here: this is a password about to be stored, so it is
    # held to the same floor and ceiling as one chosen at registration.
    password: Password


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
