from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db.models import Note, WordDefinition

# A note's owner is fixed at creation time, so user_id is intentionally not updatable.
UPDATABLE_FIELDS = {"title", "content", "is_pinned"}

# Every lookup below takes the owner as a required argument rather than an
# optional filter. That is deliberate: an optional one defaults to "any user"
# when a caller forgets it, which is silent and wrong, while a required one
# makes the same mistake a TypeError the first time the tests run.


def create_note(db: Session, user_id: int, title: str, content: str | None = None) -> Note:
    """Insert a new note owned by the given user and return it."""
    note = Note(user_id=user_id, title=title, content=content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def get_note(db: Session, note_id: int, user_id: int) -> Note | None:
    """Fetch one of this user's notes. None if it is missing or is not theirs.

    Those two cases are not distinguished on purpose: the caller turns both
    into the same 404, because a different answer would confirm that a note
    exists and belongs to someone else.
    """
    stmt = (
        select(Note)
        .where(Note.id == note_id, Note.user_id == user_id)
        .options(selectinload(Note.words))
    )
    return db.scalars(stmt).first()


def list_notes(
    db: Session,
    user_id: int,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Note]:
    """Return a page of one user's notes, optionally narrowed by a title search."""
    stmt = select(Note).options(selectinload(Note.words)).where(Note.user_id == user_id)
    if search:
        stmt = stmt.where(Note.title.ilike(f"%{search}%"))
    # Most recently touched first, so the head of the list is the note the user
    # was last in. id breaks ties between rows written in the same transaction.
    stmt = stmt.order_by(Note.updated_at.desc(), Note.id.desc()).offset(skip).limit(limit)
    return list(db.scalars(stmt))


def update_note(db: Session, note_id: int, user_id: int, **fields) -> Note | None:
    """Update the given fields on one of this user's notes."""
    note = get_note(db, note_id, user_id)
    if note is None:
        return None

    for key, value in fields.items():
        if key in UPDATABLE_FIELDS and value is not None:
            setattr(note, key, value)

    db.commit()
    db.refresh(note)
    return note


def touch_note(db: Session, note_id: int, user_id: int) -> Note | None:
    """Mark a note as just-used without changing its content.

    Opening a note counts as an update for "where you left off", but an empty
    PATCH changes no attributes, so SQLAlchemy would not issue an UPDATE and
    `onupdate` would never fire. Setting the column explicitly forces it.
    """
    note = get_note(db, note_id, user_id)
    if note is None:
        return None

    note.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, note_id: int, user_id: int) -> bool:
    """Delete one of this user's notes; return True if a row was removed."""
    note = get_note(db, note_id, user_id)
    if note is None:
        return False

    db.delete(note)
    db.commit()
    return True


def add_word_to_note(db: Session, note_id: int, word_id: int, user_id: int) -> Note | None:
    """Associate an existing word definition with one of this user's notes."""
    note = get_note(db, note_id, user_id)
    word = db.get(WordDefinition, word_id)
    if note is None or word is None:
        return None

    if word not in note.words:
        note.words.append(word)
        db.commit()
        db.refresh(note)
    return note


def remove_word_from_note(db: Session, note_id: int, word_id: int, user_id: int) -> Note | None:
    """Remove the association between a word definition and this user's note."""
    note = get_note(db, note_id, user_id)
    word = db.get(WordDefinition, word_id)
    if note is None or word is None:
        return None

    if word in note.words:
        note.words.remove(word)
        db.commit()
        db.refresh(note)
    return note
