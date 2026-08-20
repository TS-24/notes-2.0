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


class ProviderCredentialWrite(BaseModel):
    provider: ProviderId
    api_key: ApiKey
    # Null means "whatever services/llm.py defaults to for this provider",
    # which is what lets a stale default be corrected in one place.
    model: str | None = Field(None, max_length=128)


class ProviderOption(BaseModel):
    """One entry in the settings dropdown."""

    id: str
    label: str
    default_model: str


class ProviderSettingsRead(BaseModel):
    """
    What the settings page is told.

    There is no field here for the key and there must never be one. `key_hint`
    is the last four characters, which is enough to recognise which key is on
    file and not enough to be one.

    `configured` is false both when no key was ever saved and when the stored
    one cannot be decrypted — see core/secrets.py. Those are the same situation
    from the reader's side: the remedy for both is to paste the key again.
    """

    configured: bool
    provider: str | None = None
    model: str | None = None
    key_hint: str | None = None
    available: list[ProviderOption]
