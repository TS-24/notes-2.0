"""
Tests for the password-reset flow: the CLI that mints a link
(app/cli.py::issue_reset), the endpoint that spends it
(app/api/auth.py::reset_password), and app/crud/password_reset.py.

The property that carries the weight: a spent, forged or expired token must be
a 400 — never a 401 (which the frontend turns into a redirect to /login and the
message is lost) and never a 500.
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

OLD_PASSWORD = "the original passphrase here"
NEW_PASSWORD = "a fresh passphrase, different"


@pytest.fixture
def account(db) -> User:
    user = User(
        username="reader",
        email="reader@example.com",
        password_hash=hash_password(OLD_PASSWORD),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def mint_token(db, user_id: int, *, expires_in: timedelta = RESET_TOKEN_TTL) -> str:
    """A reset token for `user_id`, stored the way issue_reset stores it."""
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


class TestIssueReset:
    def test_it_prints_a_link_that_resolves_to_a_valid_token(
        self, db, account, capsys
    ):
        from app.cli import issue_reset

        rc = issue_reset(db, Namespace(email=account.email))

        assert rc == 0
        url = capsys.readouterr().out.strip()
        assert "/reset-password?token=" in url
        token = url.split("token=", 1)[1]
        assert crud_reset.get_valid_by_hash(db, hash_reset_token(token)) is not None

    def test_an_unknown_email_is_an_error_and_mints_nothing(self, db, capsys):
        from app.cli import issue_reset

        rc = issue_reset(db, Namespace(email="nobody@example.com"))

        assert rc == 1
        assert db.scalars(select(PasswordResetToken)).all() == []

    def test_a_fresh_link_retires_the_previous_one(self, db, account, capsys):
        from app.cli import issue_reset

        issue_reset(db, Namespace(email=account.email))
        first = capsys.readouterr().out.strip().split("token=", 1)[1]
        issue_reset(db, Namespace(email=account.email))

        assert crud_reset.get_valid_by_hash(db, hash_reset_token(first)) is None


class TestResetPassword:
    def test_a_valid_token_changes_the_password_and_signs_in(
        self, anon_client, db, account
    ):
        token = mint_token(db, account.id)

        response = reset(anon_client, token)

        assert response.status_code == 200
        assert response.json()["access_token"]
        # New password works, old one does not.
        assert login(anon_client, account.email, NEW_PASSWORD).status_code == 200
        assert login(anon_client, account.email, OLD_PASSWORD).status_code == 401
        # The link is stamped spent.
        assert db.scalars(select(PasswordResetToken)).one().used_at is not None

    def test_the_same_link_cannot_be_used_twice(self, anon_client, db, account):
        token = mint_token(db, account.id)
        reset(anon_client, token)

        again = reset(anon_client, token, "yet another passphrase")

        assert again.status_code == 400
        assert "invalid or has expired" in again.json()["detail"]

    def test_a_forged_token_is_refused(self, anon_client, account):
        assert reset(anon_client, "not-a-real-token").status_code == 400

    def test_an_expired_token_is_refused(self, anon_client, db, account):
        token = mint_token(db, account.id, expires_in=timedelta(minutes=-1))
        before = db.get(User, account.id).password_hash

        response = reset(anon_client, token)

        assert response.status_code == 400
        # Nothing was changed on the way to the refusal.
        assert db.get(User, account.id).password_hash == before

    def test_a_short_password_is_rejected(self, anon_client, db, account):
        token = mint_token(db, account.id)

        response = reset(anon_client, token, "too short")  # 9 chars, floor is 12

        assert response.status_code == 422

    def test_bad_token_and_missing_account_answer_alike(
        self, anon_client, db, account
    ):
        token = mint_token(db, account.id)
        db.delete(account)
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

    def test_a_token_from_before_the_reset_stops_working(
        self, anon_client, db, account
    ):
        old = self.token_issued_at(
            account.id, datetime.now(timezone.utc) - timedelta(hours=1)
        )
        assert (
            anon_client.get(
                "/api/users/me", headers={"Authorization": f"Bearer {old}"}
            ).status_code
            == 200
        )

        fresh = reset(anon_client, mint_token(db, account.id)).json()["access_token"]

        assert (
            anon_client.get(
                "/api/users/me", headers={"Authorization": f"Bearer {old}"}
            ).status_code
            == 401
        )
        # The token the reset just handed back is not caught by the same check.
        assert (
            anon_client.get(
                "/api/users/me", headers={"Authorization": f"Bearer {fresh}"}
            ).status_code
            == 200
        )
