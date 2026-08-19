"""
Tests for signing out for real (app/crud/revoked_token.py, deps.py, auth.py).

Logging out used to clear the cookie and nothing else. That stops the browser
sending the token; it does not stop anyone who copied it, and the token stayed
good for the rest of its seven days. The only lever was rotating JWT_SECRET,
which signs out every account at once.

So the token now carries a `jti` and logout records it. What matters here is
that the recorded id is refused afterwards, that refusing one session does not
touch the others, and that the record is keyed to the token rather than the
account — otherwise "sign out on this laptop" would mean "sign out everywhere".
"""

from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select

from app.core.config import JWT_ALGORITHM, JWT_SECRET
from app.core.security import create_access_token
from app.crud import revoked_token as crud_revoked
from app.db.models import RevokedToken


def jti_of(token: str) -> str:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])["jti"]


class TestTokensCarryAnId:
    def test_every_token_has_a_jti(self, user):
        assert jti_of(create_access_token(user.id))

    def test_two_tokens_for_one_user_differ(self, user):
        # Without this, revoking one session revokes them all, and the id is
        # doing no more work than the user id already does.
        assert jti_of(create_access_token(user.id)) != jti_of(create_access_token(user.id))


class TestSigningOut:
    def test_logout_records_the_token(self, client, db, user):
        client.post("/api/auth/logout")

        assert db.scalars(select(RevokedToken)).one().user_id == user.id

    def test_the_token_stops_working(self, client, db):
        assert client.get("/api/users/me").status_code == 200

        client.post("/api/auth/logout")

        # The cookie is gone from a browser, but this client still presents the
        # header, which is exactly the case a stolen token represents.
        assert client.get("/api/users/me").status_code == 401

    def test_signing_out_twice_is_not_an_error(self, client):
        client.post("/api/auth/logout")

        assert client.post("/api/auth/logout").status_code == 204

    def test_another_session_of_the_same_user_survives(self, anon_client, db, user):
        laptop = create_access_token(user.id)
        phone = create_access_token(user.id)

        anon_client.headers["Authorization"] = f"Bearer {laptop}"
        anon_client.post("/api/auth/logout")

        anon_client.headers["Authorization"] = f"Bearer {phone}"
        assert anon_client.get("/api/users/me").status_code == 200

    def test_another_users_session_is_untouched(self, client, other_client):
        client.post("/api/auth/logout")

        assert other_client.get("/api/users/me").status_code == 200

    def test_logging_out_without_credentials_is_still_fine(self, anon_client, db):
        # Nothing to revoke and nothing to complain about; the caller is trying
        # to end a session it does not have, which is already the outcome.
        response = anon_client.post("/api/auth/logout")

        assert response.status_code == 204
        assert db.scalars(select(RevokedToken)).all() == []


class TestPruning:
    def test_records_are_removed_once_their_token_would_have_expired(self, db, user):
        # Built directly rather than by revoking an expired token: an expired
        # token cannot be revoked at all, since it fails to decode. The row
        # that needs pruning is one revoked while live that has since aged out.
        now = datetime.now(timezone.utc)
        db.add_all(
            [
                RevokedToken(jti="aged-out", user_id=user.id, expires_at=now - timedelta(days=1)),
                RevokedToken(jti="still-live", user_id=user.id, expires_at=now + timedelta(days=1)),
            ]
        )
        db.commit()

        removed = crud_revoked.prune_expired(db)

        # Past its expiry a token is refused whether or not it is listed, so
        # the row stops carrying information and the table would only grow.
        assert removed == 1
        assert db.scalars(select(RevokedToken)).one().jti == "still-live"

    def test_pruning_an_empty_table_is_a_no_op(self, db):
        assert crud_revoked.prune_expired(db) == 0

    def test_an_expired_token_cannot_be_revoked(self, db, user):
        # It does not need to be: it is refused on its own merits, and a row
        # for it would be pruned on sight.
        dead = create_access_token(user.id, expires_in=timedelta(seconds=-1))

        assert crud_revoked.revoke(db, dead, user.id) is None
