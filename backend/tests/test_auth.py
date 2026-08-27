"""
Tests for registration, login and logout (app/api/auth.py).

These use `anon_client` throughout: nobody is signed in when they call these
endpoints, and the default `client` fixture would have already created an
account on the email the register cases try to claim.

Registration is invite-only, so most of what matters here is refusal: a code
that does not exist, a code already spent, an email already taken. The other
half is that failures stay uninformative. Login answers the same way whether
the email is unknown or the password is wrong, because a difference between
those two is a way to enumerate who has an account.
"""

from sqlalchemy import select

from app.db.models import InviteCode, User

PASSWORD = "correct horse battery staple"


def issue_code(db, code: str = "invite-me", invited_email: str | None = None) -> InviteCode:
    row = InviteCode(code=code, invited_email=invited_email)
    db.add(row)
    db.commit()
    return row


def register(anon_client, **overrides):
    payload = {
        "username": "reader",
        "email": "reader@example.com",
        "password": PASSWORD,
        "invite_code": "invite-me",
    }
    payload.update(overrides)
    return anon_client.post("/api/auth/register", json=payload)


class TestRegister:
    def test_a_valid_invite_creates_an_account_and_returns_a_token(self, anon_client, db):
        issue_code(db)

        response = register(anon_client)

        assert response.status_code == 201
        assert response.json()["access_token"]
        assert db.scalars(select(User).where(User.email == "reader@example.com")).one()

    def test_the_password_is_not_stored_in_the_clear(self, anon_client, db):
        issue_code(db)

        register(anon_client)

        user = db.scalars(select(User).where(User.email == "reader@example.com")).one()
        assert user.password_hash != PASSWORD
        assert PASSWORD not in user.password_hash

    def test_the_response_never_carries_the_hash(self, anon_client, db):
        issue_code(db)

        body = register(anon_client).text

        assert "password" not in body or "access_token" in body
        assert "argon2" not in body

    def test_an_unknown_invite_is_refused(self, anon_client, db):
        response = register(anon_client, invite_code="no-such-code")

        assert response.status_code == 400
        assert db.scalars(select(User)).all() == []

    def test_a_code_cannot_be_used_twice(self, anon_client, db):
        issue_code(db)
        register(anon_client)

        second = register(anon_client, email="other@example.com", username="other")

        assert second.status_code == 400
        assert len(db.scalars(select(User)).all()) == 1

    def test_an_unknown_and_a_spent_code_are_refused_identically(self, anon_client, db):
        # Telling them apart would say which codes exist.
        issue_code(db)
        register(anon_client)

        spent = register(anon_client, email="a@example.com", username="a")
        unknown = register(anon_client, email="b@example.com", username="b", invite_code="nope")

        assert spent.json()["detail"] == unknown.json()["detail"]

    def test_a_taken_email_is_a_conflict(self, anon_client, db):
        issue_code(db, "one")
        issue_code(db, "two")
        register(anon_client, invite_code="one")

        response = register(anon_client, invite_code="two")

        assert response.status_code == 409

    def test_redemption_records_who_spent_the_code(self, anon_client, db):
        issue_code(db)

        register(anon_client)

        code = db.scalars(select(InviteCode)).one()
        user = db.scalars(select(User)).one()
        assert code.used_at is not None
        assert code.used_by_user_id == user.id

    def test_a_short_password_is_rejected(self, anon_client, db):
        issue_code(db)

        response = register(anon_client, password="short")

        assert response.status_code == 422
        assert db.scalars(select(User)).all() == []


class TestACodeBoundToAnEmail:
    """
    A code issued from the account page names the address it is for.

    That is what makes a leaked code worthless: whoever finds it cannot spend it
    on themselves. Codes issued from the CLI carry no address and still work for
    anyone, which is the behaviour every code had before this existed.
    """

    def test_the_address_it_was_issued_for_can_spend_it(self, anon_client, db):
        issue_code(db, invited_email="reader@example.com")

        assert register(anon_client).status_code == 201

    def test_case_is_not_what_decides_it(self, anon_client, db):
        # Stored folded, so the comparison has to fold the incoming address too.
        # Nobody types their own email the same way twice.
        issue_code(db, invited_email="reader@example.com")

        assert register(anon_client, email="Reader@Example.COM").status_code == 201

    def test_another_address_cannot_spend_it(self, anon_client, db):
        issue_code(db, invited_email="friend@example.com")

        response = register(anon_client)

        assert response.status_code == 400
        assert db.scalars(select(User)).all() == []

    def test_the_wrong_address_and_an_unknown_code_are_refused_identically(
        self, anon_client, db
    ):
        # Same reason as the spent-code case above. A distinct reply here would
        # answer "which address is this code for?" for anyone holding one.
        issue_code(db, invited_email="friend@example.com")

        mismatch = register(anon_client)
        unknown = register(anon_client, invite_code="nope")

        assert mismatch.json()["detail"] == unknown.json()["detail"]

    def test_a_code_without_an_address_still_works_for_anyone(self, anon_client, db):
        issue_code(db)

        assert register(anon_client, email="whoever@example.com").status_code == 201


class TestTheFirstAccount:
    def test_the_first_account_is_a_superuser_and_the_second_is_not(self, anon_client, db):
        # Nothing else appoints one. On an empty production database the owner
        # registers first, and that has to be enough to reach the admin views.
        issue_code(db, "one", invited_email="reader@example.com")
        issue_code(db, "two", invited_email="second@example.com")

        register(anon_client, invite_code="one")
        register(anon_client, invite_code="two", email="second@example.com", username="second")

        first, second = db.scalars(select(User).order_by(User.id)).all()
        assert first.is_superuser is True
        assert second.is_superuser is False


class TestLogin:
    def test_correct_credentials_return_a_token(self, anon_client, db):
        issue_code(db)
        register(anon_client)

        response = anon_client.post(
            "/api/auth/login", json={"email": "reader@example.com", "password": PASSWORD}
        )

        assert response.status_code == 200
        assert response.json()["access_token"]

    def test_login_sets_the_cookie_too(self, anon_client, db):
        # The body serves the SSR frontend; the cookie serves curl and /docs.
        issue_code(db)
        register(anon_client)

        response = anon_client.post(
            "/api/auth/login", json={"email": "reader@example.com", "password": PASSWORD}
        )

        assert "restyle_token" in response.cookies

    def test_a_wrong_password_is_refused(self, anon_client, db):
        issue_code(db)
        register(anon_client)

        response = anon_client.post(
            "/api/auth/login", json={"email": "reader@example.com", "password": "wrong wrong wrong"}
        )

        assert response.status_code == 401

    def test_an_unknown_email_fails_exactly_like_a_wrong_password(self, anon_client, db):
        issue_code(db)
        register(anon_client)

        wrong_password = anon_client.post(
            "/api/auth/login", json={"email": "reader@example.com", "password": "wrong wrong wrong"}
        )
        unknown_email = anon_client.post(
            "/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
        )

        assert unknown_email.status_code == wrong_password.status_code
        assert unknown_email.json()["detail"] == wrong_password.json()["detail"]

    def test_the_sentinel_hash_is_not_a_way_in(self, db, anon_client):
        # The dev user is backfilled with "!". An unparseable hash has to read
        # as a wrong password, not a 500.
        db.add(User(username="dev", email="dev@example.com", password_hash="!"))
        db.commit()

        response = anon_client.post(
            "/api/auth/login", json={"email": "dev@example.com", "password": "!"}
        )

        assert response.status_code == 401


class TestLogout:
    def test_logout_clears_the_cookie(self, anon_client, db):
        issue_code(db)
        register(anon_client)

        response = anon_client.post("/api/auth/logout")

        assert response.status_code == 204
        assert 'restyle_token=""' in response.headers.get(
            "set-cookie", ""
        ) or "Max-Age=0" in response.headers.get("set-cookie", "")
