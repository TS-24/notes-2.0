from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .word_definition import WordDefinitionRead

Title = Annotated[str, Field(min_length=1, max_length=255)]


class NoteBase(BaseModel):
    title: Title
    content: str | None = None


class NoteCreate(NoteBase):
    user_id: int


class NoteUpdate(BaseModel):
    title: Title | None = None
    content: str | None = None


class NoteRead(NoteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    words: list[WordDefinitionRead] = []
