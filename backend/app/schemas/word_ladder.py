from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Word = Annotated[str, Field(min_length=1, max_length=255)]


class WordLadderBase(BaseModel):
    word: Word
    pos: str = ""
    rungs: list[str]
    origin_index: int = 0
    # Where the unit actually sits in the sentence that was sent. The caller
    # asks about a caret; what comes back may be wider than the word under it —
    # a phrase, or a word with its article — so the span has to travel with the
    # rungs or the caller cannot know what to replace.
    start: int = 0
    end: int = 0


class WordLadderRead(WordLadderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
