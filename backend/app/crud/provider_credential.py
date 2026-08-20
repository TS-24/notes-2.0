"""
The reader's provider credential.

`user_id` is a required argument on every function here, for the reason set out
in crud/note.py: as an optional filter it silently means "any user" the first
time somebody forgets it, and for this table that would mean handing one
account's API key to another. Required makes the same mistake a TypeError.

The key is encrypted on the way in and decrypted on the way out, so no caller
above this layer ever holds the stored form and nothing outside it needs to know
the column is ciphertext.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import secrets
from ..db.models import ProviderCredential


def get(db: Session, user_id: int) -> ProviderCredential | None:
    """This user's credential row, ciphertext and all. None if they have none."""
    return db.scalars(
        select(ProviderCredential).where(ProviderCredential.user_id == user_id)
    ).first()


def get_key(db: Session, user_id: int) -> tuple[str, str, str | None] | None:
    """
    `(provider, api_key, model)` ready to hand to services/llm.py, or None.

    None covers both "never saved one" and "saved one this deployment can no
    longer decrypt" — see core/secrets.py. They are the same situation to every
    caller: there is no usable credential, and the reader has to enter it again.
    """
    row = get(db, user_id)
    if row is None:
        return None
    key = secrets.decrypt(row.api_key_encrypted)
    if key is None:
        return None
    return row.provider, key, row.model


def save(
    db: Session, user_id: int, provider: str, api_key: str, model: str | None
) -> ProviderCredential:
    """Store this user's credential, replacing whatever was there.

    An upsert rather than an insert because the table holds one row per user:
    picking a different provider is a change of mind, not a second credential.
    """
    row = get(db, user_id)
    if row is None:
        row = ProviderCredential(user_id=user_id)
        db.add(row)

    row.provider = provider
    row.api_key_encrypted = secrets.encrypt(api_key)
    row.model = model
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, user_id: int) -> bool:
    """Forget this user's credential; True if there was one to forget."""
    row = get(db, user_id)
    if row is None:
        return False

    db.delete(row)
    db.commit()
    return True
