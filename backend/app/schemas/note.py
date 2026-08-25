from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .word_definition import WordDefinitionRead

# No minimum length. "Untitled" is placeholder text in the field, not a value:
# a note the reader never named holds "", and the interface shows the word. The
# old min_length=1 is what forced every caller to invent a title to satisfy it,
# which is how the database ended up full of notes called "Untitled".
Title = Annotated[str, Field(max_length=255)]


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
    # Readable, never writable: archiving and restoring go through their own
    # routes. NoteUpdate deliberately has no counterpart — see crud/note.py,
    # where update_note skips None and so could never clear a column.
    archived_at: datetime | None = None
    words: list[WordDefinitionRead] = []
