"""
Password hashing and access tokens.

Both halves fail closed. `verify_password` returns False rather than raising on
a hash it cannot parse, and `decode_access_token` returns None rather than
raising on anything it cannot trust, so a malformed credential can only ever
become a 401 and never a 500. A 500 here would be a real leak: it tells an
attacker their input reached further into the code than a rejection would.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

from .config import ACCESS_TOKEN_TTL, JWT_ALGORITHM, JWT_SECRET

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password for storage. Salted per call, so equal passwords differ."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Check a password against a stored hash, False on anything unparseable.

    The dev user is backfilled with "!", which no argon2 hash can equal, so
    that row is unloggable-into by construction. That has to read as a wrong
    password rather than an error.
    """
    try:
        return _hasher.verify(password_hash, password)
    except (Argon2Error, InvalidHashError):
        return False


@dataclass(frozen=True)
class TokenClaims:
    """What a token says about itself, once the signature has been trusted."""

    user_id: int
    jti: str
    expires_at: datetime
    # When the token was minted. Compared against the account's
    # password_changed_at so a reset can retire every session issued before it.
    issued_at: datetime


def create_access_token(user_id: int, expires_in: timedelta | None = None) -> str:
    """Sign a token naming the user it belongs to.

    `sub` is a string because PyJWT rejects a non-string subject on decode;
    passing the int straight through produces tokens this codebase can create
    but not read.

    `jti` is what makes a single session revocable. Two tokens for the same
    account differ by it, so signing out of one browser does not sign out the
    others — which is what would happen if revocation were keyed on the user.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + (expires_in if expires_in is not None else ACCESS_TOKEN_TTL),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenClaims | None:
    """What a token claims, or None if it cannot be trusted.

    None covers every failure worth distinguishing nowhere: a bad signature, an
    expired token, a missing or non-numeric subject, an absent id. The caller
    turns all of them into the same 401, because telling them apart would tell
    an attacker which part of their forgery to fix.

    A token minted before `jti` existed has none, and is rejected rather than
    waved through: it cannot be revoked, so accepting it would be a hole that
    closes only when the last of them expires.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return TokenClaims(
            user_id=int(payload["sub"]),
            jti=str(payload["jti"]),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            issued_at=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
        )
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None


def new_reset_token() -> str:
    """A random token for a password-reset link.

    Never stored — only `hash_reset_token` of it is. 32 bytes of urlsafe base64
    is the same strength `jti` uses, and short enough to sit in a query string.
    """
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """The SHA-256 of a reset token, hex.

    A fast hash on purpose: the token is already high-entropy random, so argon2
    here would spend CPU to protect against a dictionary attack that cannot
    apply. This is the value that goes in the database; the token itself only
    ever lives in the emailed link.
    """
    return hashlib.sha256(token.encode()).hexdigest()
