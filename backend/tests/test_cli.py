"""
Tests for the administrative commands (app/cli.py).

The one worth writing carefully is adoption. It runs once, by hand, against
the only copy of the data that matters, and it deletes an account when it is
done — so the cases that matter are the ones where it should refuse.
"""

import argparse

from sqlalchemy import select

from app.cli import DEV_USER_EMAIL, adopt_dev_data, issue_invite, promote_user
from app.db.models import InviteCode, Note, User

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


class TestIssuingFromTheCommandLine:
    def test_a_code_with_no_address_is_bound_to_nobody(self, db, capsys):
        # This is the one that makes the first account possible: there is no
        # form to reach and no address to name until somebody is already here.
        assert issue_invite(db, argparse.Namespace(email=None)) == 0

        assert db.scalars(select(InviteCode)).one().invited_email is None

    def test_an_address_can_be_named(self, db, capsys):
        issue_invite(db, argparse.Namespace(email="Friend@Example.COM"))

        assert db.scalars(select(InviteCode)).one().invited_email == "friend@example.com"


class TestPromotion:
    def test_an_account_can_be_made_a_superuser(self, db, capsys):
        user = make_user(db, "heir@example.com")

        assert promote_user(db, argparse.Namespace(email="heir@example.com")) == 0

        db.expire_all()
        assert db.get(User, user.id).is_superuser is True

    def test_an_unknown_address_fails_rather_than_saying_nothing(self, db, capsys):
        assert promote_user(db, argparse.Namespace(email="nobody@example.com")) == 1

    def test_promoting_twice_is_harmless(self, db, capsys):
        make_user(db, "heir@example.com")
        promote_user(db, argparse.Namespace(email="heir@example.com"))

        assert promote_user(db, argparse.Namespace(email="heir@example.com")) == 0
