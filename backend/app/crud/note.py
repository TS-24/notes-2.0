from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db.models import Note, WordDefinition

UPDATABLE_FIELDS = {"title", "content", "user_id"}


def create_note(db: Session, user_id: int, title: str, content: str | None = None) -> Note:
    """Insert a new note owned by the given user and return it."""
    note = Note(user_id=user_id, title=title, content=content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def get_note(db: Session, note_id: int) -> Note | None:
    """Fetch a single note by primary key."""
    stmt = select(Note).where(Note.id == note_id).options(selectinload(Note.words))
    return db.scalars(stmt).first()


def list_notes(db: Session, user_id: int | None = None, skip: int = 0, limit: int = 100) -> list[Note]:
    """Return a page of notes, optionally filtered to one user."""
    stmt = select(Note).options(selectinload(Note.words))
    if user_id is not None:
        stmt = stmt.where(Note.user_id == user_id)
    stmt = stmt.order_by(Note.id).offset(skip).limit(limit)
    return list(db.scalars(stmt))


def update_note(db: Session, note_id: int, **fields) -> Note | None:
    """Update the given fields on a note and return the updated row."""
    note = get_note(db, note_id)
    if note is None:
        return None

    for key, value in fields.items():
        if key in UPDATABLE_FIELDS and value is not None:
            setattr(note, key, value)

    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, note_id: int) -> bool:
    """Delete a note; return True if a row was removed."""
    note = db.get(Note, note_id)
    if note is None:
        return False

    db.delete(note)
    db.commit()
    return True


def add_word_to_note(db: Session, note_id: int, word_id: int) -> Note | None:
    """Associate an existing word definition with a note."""
    note = get_note(db, note_id)
    word = db.get(WordDefinition, word_id)
    if note is None or word is None:
        return None

    if word not in note.words:
        note.words.append(word)
        db.commit()
        db.refresh(note)
    return note


def remove_word_from_note(db: Session, note_id: int, word_id: int) -> Note | None:
    """Remove the association between a word definition and a note."""
    note = get_note(db, note_id)
    word = db.get(WordDefinition, word_id)
    if note is None or word is None:
        return None

    if word in note.words:
        note.words.remove(word)
        db.commit()
        db.refresh(note)
    return note
