"""
Tests for issuing invites from the account page (app/api/invites.py).

Invites used to come only from the CLI, which meant handing someone a code
required a shell on the machine running the database. These endpoints move that
to `/settings`, where any signed-in user can do it.

Two properties carry most of the weight here. A code is bound to the email it
was issued for, so a code that leaks is worth nothing to whoever finds it. And
one user's codes are not another's to read: the listing is scoped to the caller,
and the unscoped view of every invite in the system is the superuser's alone.

The `user` and `other_user` fixtures are inserted by `make_user`, which writes
the row directly and so never trips the "first account is a superuser" rule in
crud.user.create_user. Any test that wants that flag sets it itself, which is
what keeps these cases from depending on the order rows happened to be made in.
"""

import pytest
from sqlalchemy import select

from app.db.models import InviteCode, User


@pytest.fixture
def superuser(db, user: User) -> User:
    """`user`, promoted. The flag is the only difference from the default."""
    user.is_superuser = True
    db.commit()
    db.refresh(user)
    return user


class TestIssuing:
    def test_a_code_comes_back_bound_to_the_email_it_was_issued_for(self, client, db):
        response = client.post("/api/invites", json={"email": "friend@example.com"})

        assert response.status_code == 201
        body = response.json()
        assert body["code"]
        assert body["invited_email"] == "friend@example.com"
        assert body["used_at"] is None

        row = db.scalars(select(InviteCode)).one()
        assert row.code == body["code"]

    def test_the_email_is_stored_folded_so_the_check_has_one_form_to_compare(
        self, client, db
    ):
        client.post("/api/invites", json={"email": "Friend@Example.COM"})

        assert db.scalars(select(InviteCode)).one().invited_email == "friend@example.com"

    def test_the_issuer_is_recorded(self, client, db, user):
        client.post("/api/invites", json={"email": "friend@example.com"})

        assert db.scalars(select(InviteCode)).one().issued_by_user_id == user.id

    def test_an_email_that_already_has_an_account_is_refused(self, client, db, other_user):
        response = client.post("/api/invites", json={"email": other_user.email})

        # A code for an address that can never redeem it is a dead end, and the
        # issuer finds out only when the person they sent it to tries to use it.
        assert response.status_code == 409
        assert db.scalars(select(InviteCode)).all() == []

    def test_an_account_is_found_whatever_case_it_registered_in(self, client, db):
        # Emails are stored as typed, so an account may be on file as
        # "Friend@Example.com" while the issuer types "friend@example.com".
        # Comparing exactly would miss it and hand out a code that the 409
        # above exists to prevent: one nobody can ever redeem.
        db.add(User(username="mixed", email="Mixed@Example.com", password_hash="!"))
        db.commit()

        response = client.post("/api/invites", json={"email": "mixed@example.com"})

        assert response.status_code == 409
        assert db.scalars(select(InviteCode)).all() == []

    def test_something_that_is_not_an_email_is_refused(self, client, db):
        response = client.post("/api/invites", json={"email": "not-an-email"})

        assert response.status_code == 422
        assert db.scalars(select(InviteCode)).all() == []

    def test_a_stranger_cannot_issue_one(self, anon_client, db):
        response = anon_client.post("/api/invites", json={"email": "friend@example.com"})

        assert response.status_code == 401
        assert db.scalars(select(InviteCode)).all() == []


class TestListing:
    def test_the_listing_holds_the_code_so_a_lost_one_can_be_read_again(self, client):
        issued = client.post("/api/invites", json={"email": "friend@example.com"}).json()

        listing = client.get("/api/invites").json()

        assert [row["code"] for row in listing] == [issued["code"]]

    def test_one_users_codes_are_not_another_s_to_read(self, client, other_client):
        client.post("/api/invites", json={"email": "friend@example.com"})

        assert other_client.get("/api/invites").json() == []

    def test_a_cli_issued_code_belongs_to_nobody_and_shows_in_no_listing(self, client, db):
        db.add(InviteCode(code="from-the-cli"))
        db.commit()

        assert client.get("/api/invites").json() == []


class TestTheSuperuserViews:
    def test_an_ordinary_user_cannot_see_every_invite(self, client):
        assert client.get("/api/invites/all").status_code == 403

    def test_an_ordinary_user_cannot_see_every_account(self, client):
        assert client.get("/api/users").status_code == 403

    def test_a_stranger_cannot_either(self, anon_client):
        assert anon_client.get("/api/invites/all").status_code == 401
        assert anon_client.get("/api/users").status_code == 401

    def test_the_superuser_sees_a_code_somebody_else_issued_and_who_issued_it(
        self, superuser, client, other_client, other_user
    ):
        other_client.post("/api/invites", json={"email": "friend@example.com"})

        listing = client.get("/api/invites/all").json()

        assert len(listing) == 1
        assert listing[0]["invited_email"] == "friend@example.com"
        assert listing[0]["issued_by_email"] == other_user.email
        assert listing[0]["used_by_email"] is None

    def test_the_superuser_sees_every_account(self, superuser, client, other_user):
        emails = [row["email"] for row in client.get("/api/users").json()]

        assert sorted(emails) == sorted([superuser.email, other_user.email])

    def test_the_account_listing_never_carries_a_password_hash(
        self, superuser, client, other_user
    ):
        assert "password_hash" not in client.get("/api/users").text
        assert "argon2" not in client.get("/api/users").text
