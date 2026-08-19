from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .word_definition import WordDefinitionRead

Title = Annotated[str, Field(min_length=1, max_length=255)]


class NoteBase(BaseModel):
    title: Title
    content: str | None = None


class NoteCreate(NoteBase):
    # No user_id. The owner is whoever the token names; letting the body say
    # otherwise meant any caller could file a note under another account.
    pass


class NoteUpdate(BaseModel):
    title: Title | None = None
    content: str | None = None
    is_pinned: bool | None = None


class NoteRead(NoteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    is_pinned: bool
    created_at: datetime
    updated_at: datetime
    words: list[WordDefinitionRead] = []
