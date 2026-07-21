from sqlalchemy.orm import Session

from ..db.models import WordDefinition


def create_word_definition(db: Session, word: str, definition: str | None = None) -> WordDefinition:
    """Insert a new word definition and return it."""
    ...


def get_word_definition(db: Session, word_id: int) -> WordDefinition | None:
    """Fetch a single word definition by primary key."""
    ...


def get_word_definition_by_word(db: Session, word: str) -> WordDefinition | None:
    """Fetch a single word definition by its word text."""
    ...


def list_word_definitions(db: Session, skip: int = 0, limit: int = 100) -> list[WordDefinition]:
    """Return a page of word definitions."""
    ...


def update_word_definition(db: Session, word_id: int, **fields) -> WordDefinition | None:
    """Update the given fields on a word definition and return the updated row."""
    ...


def delete_word_definition(db: Session, word_id: int) -> bool:
    """Delete a word definition; return True if a row was removed."""
    ...
