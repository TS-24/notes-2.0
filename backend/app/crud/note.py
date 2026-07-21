from sqlalchemy.orm import Session

from ..db.models import Note


def create_note(db: Session, user_id: int, title: str, content: str | None = None) -> Note:
    """Insert a new note owned by the given user and return it."""
    ...


def get_note(db: Session, note_id: int) -> Note | None:
    """Fetch a single note by primary key."""
    ...


def list_notes(db: Session, user_id: int | None = None, skip: int = 0, limit: int = 100) -> list[Note]:
    """Return a page of notes, optionally filtered to one user."""
    ...


def update_note(db: Session, note_id: int, **fields) -> Note | None:
    """Update the given fields on a note and return the updated row."""
    ...


def delete_note(db: Session, note_id: int) -> bool:
    """Delete a note; return True if a row was removed."""
    ...


def add_word_to_note(db: Session, note_id: int, word_id: int) -> Note | None:
    """Associate an existing word definition with a note."""
    ...


def remove_word_from_note(db: Session, note_id: int, word_id: int) -> Note | None:
    """Remove the association between a word definition and a note."""
    ...
