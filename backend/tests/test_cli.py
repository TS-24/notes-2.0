"""
Tests for the administrative commands (app/cli.py).

The one worth writing carefully is adoption. It runs once, by hand, against
the only copy of the data that matters, and the failure it can have is not a
crash: known_words is unique on (user_id, word), so a word both accounts know
collides the moment the rows are reassigned. That case only appears on real
data, which is exactly when you least want to find it.
"""

import argparse

from sqlalchemy import select

from app.cli import DEV_USER_EMAIL, adopt_dev_data
from app.db.models import KnownWord, Note, User

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

    def test_known_words_move_too(self, db, capsys):
        dev = dev_user(db)
        heir = make_user(db, "heir@example.com")
        db.add(KnownWord(user_id=dev.id, word="felicitous"))
        db.commit()

        adopt(db, "heir@example.com")

        word = db.scalars(select(KnownWord)).one()
        assert word.user_id == heir.id

    def test_a_word_both_accounts_know_does_not_collide(self, db, capsys):
        # The unique constraint on (user_id, word) makes this the one case that
        # would fail on real data and never in a fresh test database.
        dev = dev_user(db)
        heir = make_user(db, "heir@example.com")
        db.add_all(
            [
                KnownWord(user_id=dev.id, word="arduous"),
                KnownWord(user_id=heir.id, word="arduous"),
                KnownWord(user_id=dev.id, word="brevity"),
            ]
        )
        db.commit()

        assert adopt(db, "heir@example.com") == 0

        words = sorted(w.word for w in db.scalars(select(KnownWord)))
        assert words == ["arduous", "brevity"]
        assert all(w.user_id == heir.id for w in db.scalars(select(KnownWord)))

    def test_an_unknown_heir_changes_nothing(self, db, capsys):
        dev = dev_user(db)
        db.add(Note(user_id=dev.id, title="Still the dev user's"))
        db.commit()

        assert adopt(db, "nobody@example.com") == 1

        assert db.scalars(select(Note)).one().user_id == dev.id
        assert db.scalars(select(User).where(User.email == DEV_USER_EMAIL)).first() is not None

    def test_running_it_twice_is_harmless(self, db, capsys):
        dev_user(db)
        make_user(db, "heir@example.com")

        adopt(db, "heir@example.com")

        assert adopt(db, "heir@example.com") == 0
