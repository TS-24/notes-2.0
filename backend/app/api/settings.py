"""
The reader's provider credentials, and which one they are chatting with.

Every route here is about the signed-in account and none of them takes a user
id, for the same reason users.py gives: an id in the path is an invitation to
forget comparing it to the caller, and this table holds API keys.

Saving a key calls the provider before storing anything. That is a reversal of
how this file used to work, and it is deliberate: the old note here argued that
a network call inside a settings save would fail for reasons that have nothing
to do with the key. It would — and being told *that*, in the dialog that just
asked for the key, is still better than a credential accepted in silence and a
chat that fails days later. The same call fills the model picker, so on most
providers the check costs nothing extra — see `llm.check_key` for the two where
it costs one token.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..crud import provider_credential as crud_credential
from ..db.database import get_db
from ..db.models import User
from ..schemas.provider import (
    ActiveModel,
    ActiveModelWrite,
    ConfiguredProvider,
    ProviderKeyWrite,
    ProviderOption,
    ProviderSettingsRead,
)
from ..services import llm
from .deps import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])

# The dialog's dropdown, built from the registry so the form and the thing that
# validates it can never offer different sets.
AVAILABLE = [
    ProviderOption(id=key, label=p.label, default_model=p.default_model)
    for key, p in llm.PROVIDERS.items()
]


def _no_key(provider: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"There is no key on file for {provider}.",
    )


def _catalogue(provider: str, api_key: str) -> list[str]:
    """
    What this key can reach, once the provider has agreed it is a key at all.

    A 502 rather than a 400: the request was fine, the provider is the thing
    that would not have it. The provider's own words are kept because they are
    the only thing that tells a wrong key from a spent quota from a service that
    is down — with the key itself taken back out of them first.
    """
    try:
        return llm.check_key(provider, api_key)
    except llm.ProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"That key would not answer. {llm.scrub(str(error), api_key)}",
        )


def _preferred(provider: str, models: list[str]) -> str:
    """
    The model to start on for a provider whose catalogue just arrived.

    The registry's default is a guess written whenever this file was last
    edited, so it is used only if the provider still offers it. Otherwise the
    first thing it does offer — anything real beats a name that would fail.
    """
    known = llm.PROVIDERS.get(provider)
    default = known.default_model if known else None
    return default if default in models else models[0]


def _settings(db: Session, user: User) -> ProviderSettingsRead:
    """
    What the settings dialog and the chat's picker are both shown. Never a key.

    A credential whose key cannot be decrypted is left out entirely — that is
    what it is from the reader's side, and `active` resolves to None with it.
    """
    configured = []
    for row in crud_credential.list_for_user(db, user.id):
        key = crud_credential.get_key(db, user.id, row.provider)
        if key is None:
            continue
        configured.append(
            ConfiguredProvider(
                provider=row.provider,
                label=llm.PROVIDERS[row.provider].label
                # A provider that has since left the registry: still a key on
                # file, and the reader should be able to see and forget it.
                if row.provider in llm.PROVIDERS
                else row.provider,
                key_hint=key[-4:],
                models=row.models or [],
                models_fetched_at=row.models_fetched_at,
            )
        )

    in_use = crud_credential.active(db, user)
    return ProviderSettingsRead(
        available=AVAILABLE,
        configured=configured,
        active=ActiveModel(provider=in_use[0], model=in_use[2]) if in_use else None,
    )


@router.get("/providers", response_model=ProviderSettingsRead)
def read_providers(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProviderSettingsRead:
    """Which keys are on file, what could be added, and what is in use."""
    return _settings(db, current_user)


@router.put("/providers/{provider}", response_model=ProviderSettingsRead)
def save_provider_key(
    provider: str,
    payload: ProviderKeyWrite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProviderSettingsRead:
    """
    Store a key for one provider, after checking that it works.

    Nothing is written until the provider has answered, so a rejected key leaves
    the account exactly as it was — including a working key for the same
    provider that somebody was trying to replace.

    The first key an account saves becomes the one it chats with. Later ones do
    not take over: adding a second provider is not a decision to switch to it,
    and the picker in the chat is where switching happens.
    """
    if provider not in llm.PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown provider: {provider}",
        )

    models = _catalogue(provider, payload.api_key)
    crud_credential.save(
        db,
        user_id=current_user.id,
        provider=provider,
        api_key=payload.api_key,
        models=models,
    )

    if crud_credential.active(db, current_user) is None:
        crud_credential.set_active(db, current_user, provider, _preferred(provider, models))

    return _settings(db, current_user)


@router.post("/providers/{provider}/refresh", response_model=ProviderSettingsRead)
def refresh_provider_models(
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProviderSettingsRead:
    """
    Ask the stored key what it can reach now.

    The reason the cached list is not a problem: a model added or retired since
    the key was saved is one button away, rather than a reason to paste the
    credential again.
    """
    key = crud_credential.get_key(db, current_user.id, provider)
    if key is None:
        raise _no_key(provider)

    models = _catalogue(provider, key)
    crud_credential.set_models(db, user_id=current_user.id, provider=provider, models=models)

    # A retired model would otherwise leave the account pointed at something the
    # provider no longer has, and every chat would fail on the model name.
    if current_user.active_provider == provider and current_user.active_model not in models:
        crud_credential.set_active(db, current_user, provider, _preferred(provider, models))

    return _settings(db, current_user)


@router.put("/active-model", response_model=ProviderSettingsRead)
def choose_model(
    payload: ActiveModelWrite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProviderSettingsRead:
    """
    Chat with this provider and this model from now on.

    Both halves are checked against what is actually on file. A model that the
    provider never listed is a stale tab or a typo, and accepting it would move
    the failure to the next thing the reader says, where the remedy is much
    harder to see.
    """
    row = crud_credential.get(db, current_user.id, payload.provider)
    if row is None or crud_credential.get_key(db, current_user.id, payload.provider) is None:
        raise _no_key(payload.provider)

    if payload.model not in (row.models or []):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{payload.provider} does not offer {payload.model}. Refresh its models.",
        )

    crud_credential.set_active(db, current_user, payload.provider, payload.model)
    return _settings(db, current_user)


@router.delete("/providers/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def forget_provider_key(
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    Forget one provider's key. Not an error when there is none to forget.

    If it was the one in use, the account falls to another key it holds rather
    than to nothing — an account with a working credential that refuses to chat
    would be a puzzle with no clue on screen.
    """
    crud_credential.delete(db, user_id=current_user.id, provider=provider)

    if current_user.active_provider == provider:
        remaining = _settings(db, current_user).configured
        successor = next((c for c in remaining if c.models), None)
        crud_credential.set_active(
            db,
            current_user,
            successor.provider if successor else None,
            _preferred(successor.provider, successor.models) if successor else None,
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
