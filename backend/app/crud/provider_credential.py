"""
The reader's provider credentials — one row per provider they hold a key for.

`user_id` is a required argument on every function here, for the reason set out
in crud/note.py: as an optional filter it silently means "any user" the first
time somebody forgets it, and for this table that would mean handing one
account's API key to another. Required makes the same mistake a TypeError.

The key is encrypted on the way in and decrypted on the way out, so no caller
above this layer ever holds the stored form and nothing outside it needs to know
the column is ciphertext.

Which credential is *in use* is not stored here — it is `active_provider` and
`active_model` on the user, because it is one fact about the account rather than
one per key. `active()` at the foot of this file is where the two meet.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import secrets
from ..db.models import ProviderCredential, User


def get(db: Session, user_id: int, provider: str) -> ProviderCredential | None:
    """This user's credential for one provider, ciphertext and all."""
    return db.scalars(
        select(ProviderCredential).where(
            ProviderCredential.user_id == user_id,
            ProviderCredential.provider == provider,
        )
    ).first()


def list_for_user(db: Session, user_id: int) -> list[ProviderCredential]:
    """Every credential this user holds, in the order they were first saved."""
    return list(
        db.scalars(
            select(ProviderCredential)
            .where(ProviderCredential.user_id == user_id)
            .order_by(ProviderCredential.id)
        )
    )


def get_key(db: Session, user_id: int, provider: str) -> str | None:
    """
    The plain key for one provider, or None.

    None covers both "never saved one" and "saved one this deployment can no
    longer decrypt" — see core/secrets.py. They are the same situation to every
    caller: there is no usable credential, and the reader has to enter it again.
    """
    row = get(db, user_id, provider)
    if row is None:
        return None
    return secrets.decrypt(row.api_key_encrypted)


def save(
    db: Session, user_id: int, provider: str, api_key: str, models: list[str]
) -> ProviderCredential:
    """Store a key for one provider, replacing whatever was there for it.

    An upsert on the (user, provider) pair rather than an insert: pasting a
    fresh OpenAI key is a replacement, while pasting an Anthropic one alongside
    it is a second credential. Saving another provider leaves this one alone.

    `models` is what the key could reach when it was checked, which the caller
    has already had to fetch in order to know the key works at all.
    """
    row = get(db, user_id, provider)
    if row is None:
        row = ProviderCredential(user_id=user_id, provider=provider)
        db.add(row)

    row.api_key_encrypted = secrets.encrypt(api_key)
    row.models = models
    row.models_fetched_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def set_models(
    db: Session, user_id: int, provider: str, models: list[str]
) -> ProviderCredential | None:
    """Replace one credential's cached catalogue. None if there is no such row."""
    row = get(db, user_id, provider)
    if row is None:
        return None

    row.models = models
    row.models_fetched_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, user_id: int, provider: str) -> bool:
    """Forget one provider's key; True if there was one to forget."""
    row = get(db, user_id, provider)
    if row is None:
        return False

    db.delete(row)
    db.commit()
    return True


def set_active(db: Session, user: User, provider: str | None, model: str | None) -> None:
    """Point the account at a provider and model, or at nothing."""
    user.active_provider = provider
    user.active_model = model
    db.commit()


def active(db: Session, user: User) -> tuple[str, str, str] | None:
    """
    `(provider, api_key, model)` ready to hand to services/llm.py, or None.

    The selection on the user is a pair of plain strings, so it can outlive the
    credential it names — the key can be forgotten, or stop decrypting, without
    the columns changing. Resolving it against the stored row here is what keeps
    "there is a usable credential" a single question with one answer, rather
    than something each caller checks in its own way and gets wrong differently.
    """
    if user.active_provider is None:
        return None

    key = get_key(db, user.id, user.active_provider)
    if key is None:
        return None

    row = get(db, user.id, user.active_provider)
    catalogue = (row.models if row else None) or []
    model = user.active_model
    # A model that is no longer in the catalogue would fail at the provider with
    # nothing on screen to explain it. The refresh route moves the selection
    # when it notices a model has been retired; this is the same guard for a row
    # that has not been refreshed since.
    if catalogue and model not in catalogue:
        model = catalogue[0]
    if model is None:
        return None
    return user.active_provider, key, model
