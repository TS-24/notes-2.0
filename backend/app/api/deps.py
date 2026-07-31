"""Shared API dependencies."""

from fastapi import Depends
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import User
from ..db.seed import ensure_dev_user


def get_current_user(db: Session = Depends(get_db)) -> User:
    """The user that owns the current request.

    There is no authentication yet, so this always resolves to the seeded
    development user. When real auth arrives, only this function changes:
    every route that depends on it keeps working unmodified.
    """
    return ensure_dev_user(db)
