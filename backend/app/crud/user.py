from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import User

UPDATABLE_FIELDS = {"username", "email"}


def create_user(db: Session, username: str, email: str, password_hash: str) -> User:
    """Insert a new user and return it.

    Takes a hash rather than a password: this module has no business seeing a
    plaintext one, and a signature that cannot accept it cannot store it by
    mistake.
    """
    user = User(username=username, email=email, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int) -> User | None:
    """Fetch a single user by primary key."""
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a single user by their unique email."""
    return db.scalars(select(User).where(User.email == email)).first()


def list_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """Return a page of users."""
    stmt = select(User).order_by(User.id).offset(skip).limit(limit)
    return list(db.scalars(stmt))


def update_user(db: Session, user_id: int, **fields) -> User | None:
    """Update the given fields on a user and return the updated row."""
    user = db.get(User, user_id)
    if user is None:
        return None

    for key, value in fields.items():
        if key in UPDATABLE_FIELDS and value is not None:
            setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> bool:
    """Delete a user; return True if a row was removed."""
    user = db.get(User, user_id)
    if user is None:
        return False

    db.delete(user)
    db.commit()
    return True
