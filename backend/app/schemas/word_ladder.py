from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Word = Annotated[str, Field(min_length=1, max_length=255)]


class WordLadderBase(BaseModel):
    word: Word
    pos: str = ""
    rungs: list[str]
    origin_index: int = 0


class WordLadderRead(WordLadderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
