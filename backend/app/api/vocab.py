from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..crud import word_ladder as crud_word_ladder
from ..db.database import get_db
from ..schemas.word_ladder import WordLadderRead

router = APIRouter(prefix="/vocab", tags=["vocab"])

# Long enough for any sentence, short enough that a whole note cannot be pushed
# through the query string.
MAX_SENTENCE = 2000


@router.get("/ladder", response_model=WordLadderRead)
def read_word_ladder(
    sentence: str = Query(..., min_length=1, max_length=MAX_SENTENCE),
    caret: int = Query(..., ge=0, description="Offset of the caret within `sentence`"),
    db: Session = Depends(get_db),
) -> WordLadderRead:
    """
    The difficulty ladder for whatever the caret is standing in, plainest first.

    The caller sends a caret rather than a word because the unit is not always
    the word under it: "give up" has a ladder neither of its words can reach,
    and an article has to travel with the word it attaches to so that "an
    example" can become "a model". The resolved span comes back as `start` and
    `end` so the caller knows what to replace.

    The whole ladder comes back in one response rather than a rung at a time:
    the roller's animation is 460ms, and a network round trip inside it would
    stall the reel. One request per unit, then every press is instant.

    A unit with nothing to offer is not an error — it comes back as a
    single-rung ladder, and the roller simply has nowhere to climb.
    """
    found = crud_word_ladder.get_or_build_for_caret(db, sentence, caret)
    if found is None:
        # The caret is not inside a word at all — whitespace, or punctuation.
        return WordLadderRead(
            id=0, word="", pos="", rungs=[], origin_index=0, start=caret, end=caret
        )

    ladder, unit = found
    return WordLadderRead(
        id=ladder.id,
        word=ladder.word,
        pos=ladder.pos,
        rungs=ladder.rungs,
        origin_index=ladder.origin_index,
        start=unit.start,
        end=unit.end,
    )
