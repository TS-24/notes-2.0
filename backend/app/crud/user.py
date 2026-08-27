from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import User

UPDATABLE_FIELDS = {"username", "email"}


def create_user(db: Session, username: str, email: str, password_hash: str) -> User:
    """Insert a new user and return it.

    Takes a hash rather than a password: this module has no business seeing a
    plaintext one, and a signature that cannot accept it cannot store it by
    mistake.

    The first account on an empty database becomes the superuser. That lives
    here rather than in the register endpoint so the CLI's `create-user` and the
    public registration cannot disagree about it — on a fresh deployment either
    one might be the first through the door. Two simultaneous first
    registrations could both see an empty table and both win; the result is two
    superusers on a database that had none, which is not worth a lock to avoid.
    """
    first = db.scalars(select(User.id).limit(1)).first() is None
    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        is_superuser=first,
    )
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


def get_user_by_email_folded(db: Session, email: str) -> User | None:
    """Fetch a user by email, ignoring case.

    Emails are stored as the person typed them, so the same address can be on
    file as `Friend@Example.com` and asked for as `friend@example.com`. The
    exact-match lookup above is what login uses and is left alone; this is for
    the places that are asking "is anyone already here under this address",
    where matching exactly would answer no and be wrong.
    """
    return db.scalars(select(User).where(func.lower(User.email) == email.lower())).first()


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
