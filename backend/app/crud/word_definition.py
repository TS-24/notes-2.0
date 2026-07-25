from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import WordDefinition

UPDATABLE_FIELDS = {"word", "definition"}


def create_word_definition(db: Session, word: str, definition: str | None = None) -> WordDefinition:
    """Insert a new word definition and return it."""
    word_definition = WordDefinition(word=word, definition=definition)
    db.add(word_definition)
    db.commit()
    db.refresh(word_definition)
    return word_definition


def get_word_definition(db: Session, word_id: int) -> WordDefinition | None:
    """Fetch a single word definition by primary key."""
    return db.get(WordDefinition, word_id)


def get_word_definition_by_word(db: Session, word: str) -> WordDefinition | None:
    """Fetch a single word definition by its word text."""
    stmt = select(WordDefinition).where(WordDefinition.word == word)
    return db.scalars(stmt).first()


def list_word_definitions(db: Session, skip: int = 0, limit: int = 100) -> list[WordDefinition]:
    """Return a page of word definitions."""
    stmt = select(WordDefinition).order_by(WordDefinition.id).offset(skip).limit(limit)
    return list(db.scalars(stmt))


def update_word_definition(db: Session, word_id: int, **fields) -> WordDefinition | None:
    """Update the given fields on a word definition and return the updated row."""
    word_definition = db.get(WordDefinition, word_id)
    if word_definition is None:
        return None

    for key, value in fields.items():
        if key in UPDATABLE_FIELDS and value is not None:
            setattr(word_definition, key, value)

    db.commit()
    db.refresh(word_definition)
    return word_definition


def delete_word_definition(db: Session, word_id: int) -> bool:
    """Delete a word definition; return True if a row was removed."""
    word_definition = db.get(WordDefinition, word_id)
    if word_definition is None:
        return False

    db.delete(word_definition)
    db.commit()
    return True
