from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..crud import word_ladder as crud_word_ladder
from ..db.database import get_db
from ..schemas.word_ladder import WordLadderRead

router = APIRouter(prefix="/vocab", tags=["vocab"])

# Long enough for any sentence, short enough that a whole note cannot be pushed
# through the query string.
MAX_CONTEXT = 2000


@router.get("/ladder", response_model=WordLadderRead)
def read_word_ladder(
    word: str = Query(..., min_length=1, max_length=255, description="The word to build a ladder for"),
    sentence: str = Query(
        "",
        max_length=MAX_CONTEXT,
        description="The sentence the word sits in. Only the contextual engine reads it.",
    ),
    start: int = Query(0, ge=0, description="Offset of the word within `sentence`"),
    end: int = Query(0, ge=0, description="End offset of the word within `sentence`"),
    db: Session = Depends(get_db),
) -> WordLadderRead:
    """
    The difficulty ladder for a word, plainest rung first.

    The whole ladder comes back in one response rather than a rung at a time:
    the roller's animation is 460ms, and a network round trip inside it would
    stall the reel. One request per word, then every press is instant.

    A word with nothing to offer is not an error — it comes back as a
    single-rung ladder, and the roller simply has nowhere to climb.
    """
    return crud_word_ladder.get_or_build_word_ladder(db, word, sentence, start, end)
