from sqlalchemy.orm import Session

from ..db.models import User


def create_user(db: Session, username: str, email: str) -> User:
    """Insert a new user and return it."""
    ...


def get_user(db: Session, user_id: int) -> User | None:
    """Fetch a single user by primary key."""
    ...


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a single user by their unique email."""
    ...


def list_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """Return a page of users."""
    ...


def update_user(db: Session, user_id: int, **fields) -> User | None:
    """Update the given fields on a user and return the updated row."""
    ...


def delete_user(db: Session, user_id: int) -> bool:
    """Delete a user; return True if a row was removed."""
    ...
