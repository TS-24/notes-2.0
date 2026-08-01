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
    part of the WordNet walk this cache exists to skip. "gave up" and "give up"
    are separate rows on purpose — same entry, different tense, different rungs.
    """
    cached = get_word_ladder(db, word)
    if cached is not None:
        return cached

    built = vocab.word_ladder(word)
    return _store(db, word, built)


def get_or_build_for_caret(
    db: Session, sentence: str, caret: int
) -> tuple[WordLadder, vocab.Unit] | None:
    """
    The ladder for whatever the caret is standing in.

    Returns the unit alongside the ladder because the caller asked about a
    caret, and what comes back may be wider than the word under it — a phrase,
    or a word with its article. Only the ladder is cached; the span is a
    property of this sentence, not of the unit.
    """
    unit = vocab.unit_at(sentence, caret)
    if unit is None:
        return None

    cached = get_word_ladder(db, unit.text)
    if cached is not None:
        return cached, unit

    built = vocab.unit_ladder(sentence, caret)
    if built is None:
        return None
    return _store(db, unit.text, built[1]), unit


def _store(db: Session, key: str, built: vocab.Ladder) -> WordLadder:
    ladder = WordLadder(
        word=key,
        pos=built.pos,
        rungs=built.rungs,
        origin_index=built.origin_index,
    )
    db.add(ladder)
    try:
        db.commit()
    except IntegrityError:
        # Two requests raced to build the same unit — chevrons are clickable
        # faster than a WordNet walk. Whoever loses takes the winner's row.
        db.rollback()
        existing = get_word_ladder(db, key)
        if existing is not None:
            return existing
        raise
    db.refresh(ladder)
    return ladder
