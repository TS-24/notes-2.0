from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.models import WordLadder
from ..services import vocab


def get_word_ladder(db: Session, word: str) -> WordLadder | None:
    """Fetch a cached ladder for exactly this surface form."""
    stmt = select(WordLadder).where(WordLadder.word == word)
    return db.scalars(stmt).first()


def get_or_build_word_ladder(db: Session, word: str) -> WordLadder:
    """
    The ladder for `word`, computing and caching it on first ask.

    The lookup is on the surface form, before the word is resolved: resolving is
    part of the WordNet walk this cache exists to skip.
    """
    cached = get_word_ladder(db, word)
    if cached is not None:
        return cached

    built = vocab.word_ladder(word)
    ladder = WordLadder(
        word=built.word,
        pos=built.pos,
        rungs=built.rungs,
        origin_index=built.origin_index,
    )
    db.add(ladder)
    try:
        db.commit()
    except IntegrityError:
        # Two requests raced to build the same word — chevrons are clickable
        # faster than a WordNet walk. Whoever loses takes the winner's row.
        db.rollback()
        existing = get_word_ladder(db, word)
        if existing is not None:
            return existing
        raise
    db.refresh(ladder)
    return ladder
