import hashlib
import os

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.models import WordLadder
from ..services import vocab

# Which engine builds a ladder. "wordnet" is the dictionary one: synonyms of a
# word, no context, cached forever under the word. "mlm" is the contextual one:
# a language model fills the word's slot in its own sentence — it understands
# that "a ML model" is not millilitres, but it offers whatever fits the slot
# rather than whatever means the same, so "big" can come back with "small".
# See app/services/lexsub.py.
ENGINE = os.getenv("LADDER_ENGINE", "wordnet")


def _context_hash(sentence: str, start: int, end: int) -> str:
    """
    Identifies the exact slot a contextual ladder was built for.

    Empty for the WordNet engine, whose answers depend on nothing but the word.
    """
    if not sentence:
        return ""
    return hashlib.sha256(f"{start}:{end}:{sentence}".encode()).hexdigest()


def get_word_ladder(db: Session, word: str, context_hash: str = "") -> WordLadder | None:
    """Fetch a cached ladder for this surface form in this context."""
    stmt = select(WordLadder).where(
        WordLadder.word == word, WordLadder.context_hash == context_hash
    )
    return db.scalars(stmt).first()


def get_or_build_word_ladder(
    db: Session,
    word: str,
    sentence: str = "",
    start: int = 0,
    end: int = 0,
) -> WordLadder:
    """
    The ladder for `word`, computing and caching it on first ask.

    Which engine runs is a deployment choice (`LADDER_ENGINE`), not a per-request
    one, so that a note's ladders are all built the same way.
    """
    contextual = ENGINE == "mlm" and bool(sentence)
    context_hash = _context_hash(sentence, start, end) if contextual else ""

    cached = get_word_ladder(db, word, context_hash)
    if cached is not None:
        return cached

    if contextual:
        # Imported here, not at module scope: this pulls in torch and the model
        # weights, and the WordNet engine should not pay that cost to start up.
        from ..services import lexsub

        built = lexsub.word_ladder_in_context(word, sentence, start, end)
    else:
        built = vocab.word_ladder(word)

    ladder = WordLadder(
        word=built.word,
        context_hash=context_hash,
        pos=built.pos,
        rungs=built.rungs,
        origin_index=built.origin_index,
    )
    db.add(ladder)
    try:
        db.commit()
    except IntegrityError:
        # Two requests raced to build the same word — chevrons are clickable
        # faster than a ladder can be built. Whoever loses takes the winner's row.
        db.rollback()
        existing = get_word_ladder(db, word, context_hash)
        if existing is not None:
            return existing
        raise
    db.refresh(ladder)
    return ladder
