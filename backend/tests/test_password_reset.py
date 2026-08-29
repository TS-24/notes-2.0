"""
Tests for the password-reset flow (app/api/auth.py::forgot_password /
reset_password, app/crud/password_reset.py, app/services/email.py).

Two properties carry most of the weight. First, forgot-password must answer the
same way for an address that has an account and one that does not, or it becomes
a way to enumerate users — the same rule login follows. Second, a spent, forged
or expired reset token must be a 400 and never a 401 (which the frontend turns
into a redirect) or a 500.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from app.core.config import JWT_ALGORITHM, JWT_SECRET
from app.core.security import hash_password, hash_reset_token
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


@pytest.fixture(autouse=True)
def captured_links(monkeypatch) -> list[tuple[str, str]]:
    """Intercept the outbound reset email and keep (recipient, raw token).

    The endpoint sends on a background task, which TestClient runs after the
    response — so by the time a request returns, this list is populated.
    """
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.api.auth.send_password_reset",
        lambda to, token: sent.append((to, token)),
    )
    return sent


def forgot(anon_client, email: str):
    return anon_client.post("/api/auth/forgot-password", json={"email": email})


def reset(anon_client, token: str, password: str = NEW_PASSWORD):
    return anon_client.post(
        "/api/auth/reset-password", json={"token": token, "password": password}
    )


def login(anon_client, email: str, password: str):
    return anon_client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )


class TestForgotPassword:
    def test_a_known_address_gets_one_token_and_one_email(
        self, anon_client, db, account, captured_links
    ):
        response = forgot(anon_client, account.email)

        assert response.status_code == 200
        rows = db.scalars(select(PasswordResetToken)).all()
        assert len(rows) == 1

        assert len(captured_links) == 1
        to, raw = captured_links[0]
        assert to == account.email
        # The stored value is the hash of what was emailed, never the token.
        assert rows[0].token_hash == hash_reset_token(raw)
        assert rows[0].token_hash != raw

    def test_an_unknown_address_looks_identical_and_stores_nothing(
        self, anon_client, db, account, captured_links
    ):
        known = forgot(anon_client, account.email)
        unknown = forgot(anon_client, "nobody@example.com")

        assert unknown.status_code == known.status_code
        assert unknown.json() == known.json()
        # Only the known address produced a row and an email.
        assert len(db.scalars(select(PasswordResetToken)).all()) == 1
        assert [to for to, _ in captured_links] == [account.email]

    def test_a_second_request_inside_the_window_is_a_no_op(
        self, anon_client, db, account, captured_links
    ):
        forgot(anon_client, account.email)
        second = forgot(anon_client, account.email)

        assert second.status_code == 200
        # No new row, no new email — the 60s resend guard.
        assert len(db.scalars(select(PasswordResetToken)).all()) == 1
        assert len(captured_links) == 1


class TestResetPassword:
    def _link_for(self, anon_client, captured_links, account) -> str:
        forgot(anon_client, account.email)
        return captured_links[-1][1]

    def test_a_valid_token_changes_the_password_and_signs_in(
        self, anon_client, db, account, captured_links
    ):
        token = self._link_for(anon_client, captured_links, account)

        response = reset(anon_client, token)

        assert response.status_code == 200
        assert response.json()["access_token"]
        # New password works, old one does not.
        assert login(anon_client, account.email, NEW_PASSWORD).status_code == 200
        assert login(anon_client, account.email, OLD_PASSWORD).status_code == 401
        # The link is stamped spent.
        row = db.scalars(select(PasswordResetToken)).one()
        assert row.used_at is not None

    def test_the_same_link_cannot_be_used_twice(
        self, anon_client, captured_links, account
    ):
        token = self._link_for(anon_client, captured_links, account)
        reset(anon_client, token)

        again = reset(anon_client, token, "yet another passphrase")

        assert again.status_code == 400
        assert "invalid or has expired" in again.json()["detail"]

    def test_a_forged_token_is_refused(self, anon_client, account):
        response = reset(anon_client, "not-a-real-token")

        assert response.status_code == 400

    def test_an_expired_token_is_refused(self, anon_client, db, account):
        raw = "expired-token-value"
        db.add(
            PasswordResetToken(
                user_id=account.id,
                token_hash=hash_reset_token(raw),
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        db.commit()
        before = db.get(User, account.id).password_hash

        response = reset(anon_client, raw)

        assert response.status_code == 400
        # Nothing was changed on the way to the refusal.
        assert db.get(User, account.id).password_hash == before

    def test_a_short_password_is_rejected(
        self, anon_client, captured_links, account
    ):
        token = self._link_for(anon_client, captured_links, account)

        response = reset(anon_client, token, "too short")  # 9 chars, floor is 12

        assert response.status_code == 422

    def test_bad_token_and_missing_account_answer_alike(
        self, anon_client, db, account, captured_links
    ):
        token = self._link_for(anon_client, captured_links, account)
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
        self, anon_client, db, account, captured_links
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

        forgot(anon_client, account.email)
        fresh = reset(anon_client, captured_links[-1][1]).json()["access_token"]

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


class TestEmailService:
    def test_send_email_without_smtp_warns_instead_of_raising(self, caplog):
        from app.services.email import send_email

        # WARNING, not INFO: nothing configures logging, so an INFO line would
        # be dropped at the root logger's default level and the link with it.
        with caplog.at_level("WARNING"):
            send_email("someone@example.com", "Subject here", "the body")

        assert any(r.levelname == "WARNING" for r in caplog.records)
        assert "SMTP_HOST is not set" in caplog.text
        assert "someone@example.com" in caplog.text
        assert "the body" in caplog.text
