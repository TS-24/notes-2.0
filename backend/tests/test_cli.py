"""
Tests for the administrative commands (app/cli.py).

The one worth writing carefully is adoption. It runs once, by hand, against
the only copy of the data that matters, and it deletes an account when it is
done — so the cases that matter are the ones where it should refuse.
"""

import argparse

from sqlalchemy import select

from app.cli import DEV_USER_EMAIL, adopt_dev_data
from app.db.models import Note, User

from conftest import make_user


def dev_user(db) -> User:
    user = User(username="dev", email=DEV_USER_EMAIL, password_hash="!")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def adopt(db, email: str) -> int:
    return adopt_dev_data(db, argparse.Namespace(email=email))


class TestAdoption:
    def test_notes_move_to_the_named_account(self, db, capsys):
        dev = dev_user(db)
        heir = make_user(db, "heir@example.com")
        db.add(Note(user_id=dev.id, title="Written before there were accounts"))
        db.commit()

        assert adopt(db, "heir@example.com") == 0

        note = db.scalars(select(Note)).one()
        assert note.user_id == heir.id

    def test_the_dev_user_is_removed(self, db, capsys):
        dev_user(db)
        make_user(db, "heir@example.com")

        adopt(db, "heir@example.com")

        assert db.scalars(select(User).where(User.email == DEV_USER_EMAIL)).first() is None

    def test_running_it_twice_is_harmless(self, db, capsys):
        dev_user(db)
        make_user(db, "heir@example.com")

        adopt(db, "heir@example.com")

        assert adopt(db, "heir@example.com") == 0
