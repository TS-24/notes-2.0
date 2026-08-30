"""
Tests for the password-reset flow: the superuser endpoint that issues a link
(app/api/password_resets.py), the CLI that issues one when nobody is left to
(app/cli.py::issue_reset), and the public endpoint that spends it
(app/api/auth.py::reset_password).

Three properties carry the weight. Issuing is superuser-only, because a reset
link opens an account that already exists. A spent, forged or expired token is
a 400 — never a 401, which the frontend turns into a redirect to /login where
the message is lost, and never a 500. And a reset ends the sessions that
predated it, which is the whole reason to reset an account somebody else is in.
"""

from argparse import Namespace
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from app.core.config import JWT_ALGORITHM, JWT_SECRET, RESET_TOKEN_TTL
from app.core.security import hash_password, hash_reset_token, new_reset_token
from app.crud import password_reset as crud_reset
from app.db.models import PasswordResetToken, User

# What conftest's `make_user` gives the `user` fixture.
OLD_PASSWORD = "correct horse battery"
NEW_PASSWORD = "a fresh passphrase, different"


def token_in(url: str) -> str:
    return url.split("token=", 1)[1]


def mint_token(db, user_id: int, *, expires_in: timedelta = RESET_TOKEN_TTL) -> str:
    """A reset token for `user_id`, stored the way the endpoint stores it."""
    raw = new_reset_token()
    db.add(
        PasswordResetToken(
            user_id=user_id,
            token_hash=hash_reset_token(raw),
            expires_at=datetime.now(timezone.utc) + expires_in,
        )
    )
    db.commit()
    return raw


def reset(anon_client, token: str, password: str = NEW_PASSWORD):
    return anon_client.post(
        "/api/auth/reset-password", json={"token": token, "password": password}
    )


def login(anon_client, email: str, password: str):
    return anon_client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )


@pytest.fixture
def superuser(db) -> User:
    user = User(
        username="admin",
        email="admin@example.com",
        password_hash=hash_password("an admin passphrase"),
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def super_client(anon_client, superuser):
    from app.core.security import create_access_token

    anon_client.headers["Authorization"] = f"Bearer {create_access_token(superuser.id)}"
    return anon_client


class TestIssuingIsPrivileged:
    def test_the_superuser_gets_a_link(self, super_client, db, user):
        response = super_client.post(
            "/api/password-resets", json={"email": user.email}
        )

        assert response.status_code == 201
        body = response.json()
        assert "/reset-password?token=" in body["url"]
        assert body["email"] == user.email
        assert body["expires_in_minutes"] == 60
        # What is stored is the hash of what was handed over, never the token.
        row = db.scalars(select(PasswordResetToken)).one()
        assert row.token_hash == hash_reset_token(token_in(body["url"]))
        assert row.token_hash not in body["url"]

    def test_an_ordinary_account_may_not(self, client, db, other_user):
        response = client.post(
            "/api/password-resets", json={"email": other_user.email}
        )

        assert response.status_code == 403
        assert db.scalars(select(PasswordResetToken)).all() == []

    def test_a_stranger_may_not(self, anon_client, db, user):
        response = anon_client.post(
            "/api/password-resets", json={"email": user.email}
        )

        assert response.status_code == 401
        assert db.scalars(select(PasswordResetToken)).all() == []

    def test_an_unknown_address_is_a_404(self, super_client, db):
        response = super_client.post(
            "/api/password-resets", json={"email": "nobody@example.com"}
        )

        assert response.status_code == 404
        assert db.scalars(select(PasswordResetToken)).all() == []

    def test_the_address_is_matched_regardless_of_case(self, super_client, user):
        response = super_client.post(
            "/api/password-resets", json={"email": user.email.upper()}
        )

        assert response.status_code == 201
        # Echoed back as stored, so the issuer sees which account they opened.
        assert response.json()["email"] == user.email

    def test_a_new_link_retires_the_last_one(self, super_client, db, user):
        first = token_in(
            super_client.post(
                "/api/password-resets", json={"email": user.email}
            ).json()["url"]
        )

        super_client.post("/api/password-resets", json={"email": user.email})

        assert crud_reset.get_valid_by_hash(db, hash_reset_token(first)) is None


class TestIssueResetFromTheCli:
    def test_it_prints_a_usable_link(self, db, user, capsys):
        from app.cli import issue_reset

        rc = issue_reset(db, Namespace(email=user.email))

        assert rc == 0
        url = capsys.readouterr().out.strip()
        assert crud_reset.get_valid_by_hash(db, hash_reset_token(token_in(url)))

    def test_an_unknown_email_mints_nothing(self, db, capsys):
        from app.cli import issue_reset

        rc = issue_reset(db, Namespace(email="nobody@example.com"))

        assert rc == 1
        assert db.scalars(select(PasswordResetToken)).all() == []


class TestSpendingALink:
    def test_a_valid_token_changes_the_password_and_signs_in(
        self, anon_client, db, user
    ):
        token = mint_token(db, user.id)

        response = reset(anon_client, token)

        assert response.status_code == 200
        assert response.json()["access_token"]
        assert login(anon_client, user.email, NEW_PASSWORD).status_code == 200
        assert login(anon_client, user.email, OLD_PASSWORD).status_code == 401
        assert db.scalars(select(PasswordResetToken)).one().used_at is not None

    def test_the_same_link_cannot_be_used_twice(self, anon_client, db, user):
        token = mint_token(db, user.id)
        reset(anon_client, token)

        again = reset(anon_client, token, "yet another passphrase")

        assert again.status_code == 400
        assert "invalid or has expired" in again.json()["detail"]

    def test_a_forged_token_is_refused(self, anon_client, user):
        assert reset(anon_client, "not-a-real-token").status_code == 400

    def test_an_expired_token_is_refused(self, anon_client, db, user):
        token = mint_token(db, user.id, expires_in=timedelta(minutes=-1))
        before = db.get(User, user.id).password_hash

        response = reset(anon_client, token)

        assert response.status_code == 400
        # Nothing was changed on the way to the refusal.
        assert db.get(User, user.id).password_hash == before

    def test_a_short_password_is_rejected(self, anon_client, db, user):
        token = mint_token(db, user.id)

        response = reset(anon_client, token, "too short")  # 9 chars, floor is 12

        assert response.status_code == 422

    def test_a_deleted_account_answers_like_a_bad_token(self, anon_client, db, user):
        token = mint_token(db, user.id)
        db.delete(user)
        db.commit()

        response = reset(anon_client, token)

        assert response.status_code == 400
        assert "invalid or has expired" in response.json()["detail"]


class TestSessionsAfterReset:
    def token_issued_at(self, user_id: int, when: datetime) -> str:
        return jwt.encode(
            {
                "sub": str(user_id),
                "jti": f"test-{when.timestamp()}",
                "iat": when,
                "exp": when + timedelta(days=7),
            },
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )

    def test_a_token_from_before_the_reset_stops_working(self, anon_client, db, user):
        old = self.token_issued_at(
            user.id, datetime.now(timezone.utc) - timedelta(hours=1)
        )
        assert (
            anon_client.get(
                "/api/users/me", headers={"Authorization": f"Bearer {old}"}
            ).status_code
            == 200
        )

        fresh = reset(anon_client, mint_token(db, user.id)).json()["access_token"]

        assert (
            anon_client.get(
                "/api/users/me", headers={"Authorization": f"Bearer {old}"}
            ).status_code
            == 401
        )
        # The session the reset just handed back is not caught by the same check.
        assert (
            anon_client.get(
                "/api/users/me", headers={"Authorization": f"Bearer {fresh}"}
            ).status_code
            == 200
        )

    def test_the_session_it_hands_back_outlives_its_own_stamp(
        self, anon_client, db, user
    ):
        """The reset must not refuse the session it just issued.

        `password_changed_at` and the new token's `iat` land in the same second,
        so the check in deps.py has to be strictly-before. Getting that backwards
        makes a reset appear to work and then bounce the reader straight back to
        the sign-in page — see the seam described in api/auth.py::reset_password.
        """
        fresh = reset(anon_client, mint_token(db, user.id)).json()["access_token"]

        assert (
            anon_client.get(
                "/api/users/me", headers={"Authorization": f"Bearer {fresh}"}
            ).status_code
            == 200
        )
