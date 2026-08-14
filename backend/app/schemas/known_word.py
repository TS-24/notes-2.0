from typing import Annotated

from pydantic import BaseModel, Field

from .word_definition import Word


class KnownWordsCreate(BaseModel):
    """Words the user has dismissed as already known.

    A list rather than a single word because the grid may dismiss several
    before a request goes out, and one round trip is cheaper than four.
    """

    words: Annotated[list[Word], Field(max_length=500)]
