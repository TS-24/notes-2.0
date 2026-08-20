"""
Encryption at rest for the credentials a reader lends us.

A provider API key is a bearer credential for somebody's paid account, and it is
the first thing this app stores on a *user's* behalf rather than the
deployment's. Nothing else here keeps a bearer credential in the clear, so
neither does this.

The encryption key is derived from `JWT_SECRET` rather than being a second
secret to set, forward through compose, and eventually lose. One HKDF with its
own `info` string keeps the derived key unrelated to the one signing tokens even
though both grow from the same root — so a token signature can never be confused
for key material and vice versa.

That derivation has a consequence worth stating plainly: rotating `JWT_SECRET`
is the documented way to sign everybody out, and it also makes every stored key
undecryptable. `decrypt` therefore returns None instead of raising, the way
`verify_password` and `decode_access_token` do. An orphaned credential reads as
"no credential on file", which the reader fixes by pasting the key again; a 500
would be neither explicable nor recoverable.
"""

import base64
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .config import JWT_SECRET

# Distinct from anything else derived from JWT_SECRET. Bumping the suffix would
# orphan every stored credential, so it is a version marker rather than a knob.
_INFO = b"restyle-provider-credentials-v1"


def derive_key(secret: str) -> bytes:
    """The Fernet key for a signing secret. Stable, or every restart orphans."""
    raw = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=_INFO
    ).derive(secret.encode())
    return base64.urlsafe_b64encode(raw)


@lru_cache(maxsize=2)
def fernet_for(secret: str) -> Fernet:
    """A cipher bound to one secret. Cached: HKDF on every save is waste."""
    return Fernet(derive_key(secret))


def encrypt(value: str) -> str:
    """The stored form of a credential. Never equal for two equal inputs.

    Fernet carries a random IV, so two accounts holding the same key do not
    produce the same row — which would otherwise let anyone reading the table
    learn who shares a key without decrypting anything.
    """
    return fernet_for(JWT_SECRET).encrypt(value.encode()).decode()


def decrypt(stored: str) -> str | None:
    """The credential back, or None if this deployment cannot read it.

    None covers every failure worth distinguishing nowhere: a key written under
    a rotated secret, a truncated column, a value that was never a token. The
    caller turns all of them into "add your key again", because that is the only
    remedy any of them has.
    """
    try:
        return fernet_for(JWT_SECRET).decrypt(stored.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        return None
