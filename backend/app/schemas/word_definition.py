from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Word = Annotated[str, Field(min_length=1, max_length=255)]


class WordDefinitionBase(BaseModel):
    word: Word
    definition: str | None = None


class WordDefinitionCreate(WordDefinitionBase):
    pass


class WordDefinitionUpdate(BaseModel):
    word: Word | None = None
    definition: str | None = None


class WordDefinitionRead(WordDefinitionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
