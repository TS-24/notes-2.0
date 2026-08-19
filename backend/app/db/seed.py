"""Development seeding.

The app has no authentication yet, but every note needs an owner. Until real
auth exists, all data belongs to a single seeded development user.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import User

DEV_USER_EMAIL = "dev@example.com"
DEV_USER_USERNAME = "dev"

# Not a hash any argon2 call can produce, so verify() rejects it and this
# account is unloggable-into by construction. The dev user exists to own rows
# until real accounts do; it must never be a way in.
UNUSABLE_PASSWORD_HASH = "!"


def ensure_dev_user(db: Session) -> User:
    """Return the development user, creating it on first run."""
    user = db.scalars(select(User).where(User.email == DEV_USER_EMAIL)).first()
    if user is not None:
        return user

    user = User(
        username=DEV_USER_USERNAME,
        email=DEV_USER_EMAIL,
        password_hash=UNUSABLE_PASSWORD_HASH,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
