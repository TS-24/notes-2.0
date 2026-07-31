from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .word_definition import WordDefinitionRead

Title = Annotated[str, Field(min_length=1, max_length=255)]


class NoteBase(BaseModel):
    title: Title
    content: str | None = None


class NoteCreate(NoteBase):
    # Optional: defaults to the requesting user, so clients without a user
    # concept can post just a title and content.
    user_id: int | None = None


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
