import hashlib
import os

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.models import WordLadder
from ..services import vocab


def _context_hash(sentence: str) -> str:
    """
    Identifies the sentence a ranked ladder was built for.

    Empty when ranking is off, because a dictionary ladder is a property of the
    word alone and should stay cached under it — a word met again in new prose
    is then still a hit, which is the behaviour the cache was built for.
    """
    if os.getenv("LADDER_RANKING", "on") == "off" or not sentence:
        return ""
    return hashlib.sha256(sentence.encode()).hexdigest()


def get_word_ladder(db: Session, word: str, context_hash: str = "") -> WordLadder | None:
    """Fetch a cached ladder for this unit in this context."""
    stmt = select(WordLadder).where(
        WordLadder.word == word, WordLadder.context_hash == context_hash
    )
    return db.scalars(stmt).first()


def get_or_build_word_ladder(db: Session, word: str) -> WordLadder:
    """
    The ladder for a bare word, with no sentence to read.

    "gave up" and "give up" are separate rows on purpose — same entry, different
    tense, different rungs.
    """
    cached = get_word_ladder(db, word)
    if cached is not None:
        return cached
    return _store(db, word, "", vocab.word_ladder(word))


def get_or_build_for_caret(
    db: Session, sentence: str, caret: int
) -> tuple[WordLadder, vocab.Unit] | None:
    """
    The ladder for whatever the caret is standing in.

    Resolving the unit comes first and is not cached: the cache key *is* the
    unit, and which unit it is depends on the sentence — "running through" is
    the unit in "running through the supplies" and not in "running through the
    park". Keying on the raw longest match instead would serve one sentence's
    answer to the other, which is exactly the bug this ordering avoids.
    """
    unit = vocab.resolve_unit(sentence, caret)
    if unit is None:
        return None

    context = _context_hash(sentence)
    cached = get_word_ladder(db, unit.text, context)
    if cached is not None:
        return cached, unit

    built = vocab.ladder_for_unit(sentence, unit)
    return _store(db, unit.text, context, built), unit


def _store(db: Session, key: str, context: str, built: vocab.Ladder) -> WordLadder:
    ladder = WordLadder(
        word=key,
        context_hash=context,
        pos=built.pos,
        rungs=built.rungs,
        origin_index=built.origin_index,
    )
    db.add(ladder)
    try:
        db.commit()
    except IntegrityError:
        # Two requests raced to build the same unit — chevrons are clickable
        # faster than a ladder can be built. Whoever loses takes the winner's row.
        db.rollback()
        existing = get_word_ladder(db, key, context)
        if existing is not None:
            return existing
        raise
    db.refresh(ladder)
    return ladder
