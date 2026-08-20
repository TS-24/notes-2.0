from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from ..services.llm import PROVIDERS

# The registry is the source of truth for which providers exist, so the request
# type is generated from it. A provider outside the table is a 422 from
# pydantic rather than a hand-written check that can drift out of step with the
# dropdown the frontend builds from the same list.
ProviderId = Literal[tuple(PROVIDERS)]  # type: ignore[valid-type]

# Long enough for any provider's key, short enough that the column is not a
# place to post something else. Stripped first: a key pasted with a trailing
# newline is the ordinary case, and it would otherwise be stored and sent as-is.
ApiKey = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=8, max_length=512)
]


class ProviderKeyWrite(BaseModel):
    """A key, and nothing else. Which provider it is for is in the path.

    The model is no longer part of saving a key, which is the point of the
    change: a key is a credential and a model is a choice, and pairing them
    meant re-pasting the credential every time the choice changed.
    """

    api_key: ApiKey


class ActiveModelWrite(BaseModel):
    """What the account should chat with from now on."""

    provider: ProviderId
    model: str = Field(min_length=1, max_length=128)


class ProviderOption(BaseModel):
    """One provider the account could add a key for."""

    id: str
    label: str
    default_model: str


class ConfiguredProvider(BaseModel):
    """
    One key the account holds.

    There is no field here for the key and there must never be one. `key_hint`
    is the last four characters, which is enough to recognise which key is on
    file and not enough to be one.

    A provider whose stored key cannot be decrypted does not appear at all — see
    core/secrets.py. That is the same situation as never having saved one, from
    the reader's side: the remedy for both is to paste the key again.
    """

    provider: str
    label: str
    key_hint: str
    # What the key could reach when it was last asked. The picker is built from
    # this rather than from a live call, so opening a chat costs nothing.
    models: list[str]
    models_fetched_at: datetime | None = None


class ActiveModel(BaseModel):
    """The provider and model this account is chatting with."""

    provider: str
    model: str


class ProviderSettingsRead(BaseModel):
    """What the settings dialog and the chat's picker are both told."""

    available: list[ProviderOption]
    configured: list[ConfiguredProvider]
    # Null when there is no usable key at all. The chat shows a way to /settings
    # rather than a picker with nothing in it.
    active: ActiveModel | None = None
