from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import KnownWord


def list_known_words(db: Session, user_id: int) -> set[str]:
    """Every word this user has dismissed.

    A set rather than a list because the only caller asks "is this one known?"
    once per candidate word, and the analysis runs over a whole corpus.
    """
    stmt = select(KnownWord.word).where(KnownWord.user_id == user_id)
    return set(db.scalars(stmt))


def add_known_words(db: Session, user_id: int, words: list[str]) -> int:
    """Mark words as known; return how many rows were actually added.

    Idempotent by design. The note grid removes the card before the request
    goes out and never reads the response, so a resend — a retry, a double
    click, the same word dismissed from two notes — has to be a no-op rather
    than an error the user can neither see nor act on.
    """
    wanted = {word for word in (w.strip() for w in words) if word}
    if not wanted:
        return 0

    already = list_known_words(db, user_id)
    new = wanted - already
    if not new:
        return 0

    db.add_all(KnownWord(user_id=user_id, word=word) for word in new)
    db.commit()
    return len(new)
