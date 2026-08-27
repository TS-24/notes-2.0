"""
Tests for the ownership edges of the schema (app/db/models.py).

These check the relationships rather than any route, because the cascade is the
thing a route cannot fix. Deleting an account has to take that account's data
with it: rows left pointing at a user id that no longer exists are a foreign
key error on Postgres and silent garbage on SQLite, and the difference is
invisible to a suite that only runs the second one.
"""

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import InviteCode, Note, User


def make_user(db, email: str = "reader@example.com") -> User:
    user = User(
        username=email.split("@")[0],
        email=email,
        password_hash=hash_password("correct horse battery"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestUserDeletion:
    def test_deleting_a_user_removes_their_notes(self, db):
        user = make_user(db)
        db.add(Note(user_id=user.id, title="A note"))
        db.commit()

        db.delete(user)
        db.commit()

        assert db.scalars(select(Note)).all() == []


class TestInviteCodes:
    def test_a_fresh_code_is_unused(self, db):
        code = InviteCode(code="abc123")
        db.add(code)
        db.commit()

        # Unused is the absence of a timestamp rather than a boolean, so
        # redemption records when it happened without a second column.
        assert code.used_at is None
        assert code.used_by_user_id is None

    def test_a_password_hash_is_required(self, db):
        # Accounts without a password would be accounts nobody can authenticate
        # as, and the column is what stops one being created by accident.
        assert User.__table__.c.password_hash.nullable is False
