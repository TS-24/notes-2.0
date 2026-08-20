"""
The reader's own provider credential.

Every route here is about the signed-in account and none of them takes an id,
for the same reason users.py gives: an id in the path is an invitation to forget
comparing it to the caller, and this table holds API keys.
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..crud import provider_credential as crud_credential
from ..db.database import get_db
from ..db.models import User
from ..schemas.provider import (
    ProviderCredentialWrite,
    ProviderOption,
    ProviderSettingsRead,
)
from ..services.llm import PROVIDERS
from .deps import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])

# The dropdown's contents, built from the registry so the form and the thing
# that validates it can never offer different sets.
AVAILABLE = [
    ProviderOption(id=key, label=p.label, default_model=p.default_model)
    for key, p in PROVIDERS.items()
]


def _settings(db: Session, user: User) -> ProviderSettingsRead:
    """
    What the settings page is shown. Never the key.

    `get_key` rather than `get`, so a row this deployment can no longer decrypt
    reports as unconfigured — which is what it is, from the reader's side.
    """
    usable = crud_credential.get_key(db, user.id)
    if usable is None:
        return ProviderSettingsRead(configured=False, available=AVAILABLE)

    provider, key, model = usable
    return ProviderSettingsRead(
        configured=True,
        provider=provider,
        # Resolved rather than echoed: the form should show the model that will
        # actually be called, not an empty box meaning "the default, whatever
        # that is today".
        model=model or PROVIDERS[provider].default_model,
        # Enough to recognise which key is on file, not enough to be one.
        key_hint=key[-4:],
        available=AVAILABLE,
    )


@router.get("/provider", response_model=ProviderSettingsRead)
def read_provider(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProviderSettingsRead:
    """Which provider is configured, and what could be. Never the key itself."""
    return _settings(db, current_user)


@router.put("/provider", response_model=ProviderSettingsRead)
def save_provider(
    payload: ProviderCredentialWrite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProviderSettingsRead:
    """
    Store a provider and key for this account, replacing anything before it.

    The provider is validated by the schema against the same registry the
    dropdown is built from, so an unknown one is a 422 rather than a row that
    fails much later when somebody tries to chat.

    The key is not checked against the provider here. Doing so would mean a
    network call inside a settings save, and it would fail for reasons that have
    nothing to do with the key — the first chat is where a wrong key shows up,
    and it says so there.
    """
    crud_credential.save(
        db,
        user_id=current_user.id,
        provider=payload.provider,
        api_key=payload.api_key,
        model=payload.model,
    )
    return _settings(db, current_user)


@router.delete("/provider", status_code=status.HTTP_204_NO_CONTENT)
def forget_provider(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Response:
    """Forget this account's key. Not an error when there is none to forget."""
    crud_credential.delete(db, user_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
