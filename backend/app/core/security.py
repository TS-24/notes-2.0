"""
Password hashing and access tokens.

Both halves fail closed. `verify_password` returns False rather than raising on
a hash it cannot parse, and `decode_access_token` returns None rather than
raising on anything it cannot trust, so a malformed credential can only ever
become a 401 and never a 500. A 500 here would be a real leak: it tells an
attacker their input reached further into the code than a rejection would.
"""

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


def create_access_token(user_id: int, expires_in: timedelta | None = None) -> str:
    """Sign a token naming the user it belongs to.

    `sub` is a string because PyJWT rejects a non-string subject on decode;
    passing the int straight through produces tokens this codebase can create
    but not read.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + (expires_in if expires_in is not None else ACCESS_TOKEN_TTL),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """The user id a token names, or None if it cannot be trusted.

    None covers every failure worth distinguishing nowhere: a bad signature, an
    expired token, a missing or non-numeric subject. The caller turns all of
    them into the same 401, because telling them apart would tell an attacker
    which part of their forgery to fix.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None
