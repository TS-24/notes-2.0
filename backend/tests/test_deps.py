"""
Tests for resolving the requesting user (app/api/deps.py).

/api/users/me stands in for every protected route here: it is the thinnest one
that needs a user, so what it returns is exactly what the dependency resolved.
The cases that matter are the ones where something is wrong with the
credential, because each of them has to become a 401 and not a 500 — a stack
trace tells an attacker their input got further than a rejection would.
"""

from datetime import timedelta

from app.core.security import create_access_token
from app.db.models import User


class TestCredentials:
    def test_a_bearer_token_identifies_the_user(self, client, user):
        response = client.get("/api/users/me")

        assert response.status_code == 200
        assert response.json()["email"] == user.email

    def test_a_cookie_works_too(self, anon_client, user):
        # curl and /docs use the cookie the API sets; the frontend uses Bearer.
        anon_client.cookies.set("restyle_token", create_access_token(user.id))

        response = anon_client.get("/api/users/me")

        assert response.status_code == 200
        assert response.json()["email"] == user.email

    def test_the_bearer_header_wins_over_a_cookie(self, anon_client, user, other_user):
        anon_client.cookies.set("restyle_token", create_access_token(other_user.id))
        anon_client.headers["Authorization"] = f"Bearer {create_access_token(user.id)}"

        response = anon_client.get("/api/users/me")

        assert response.json()["email"] == user.email


class TestRefusals:
    def test_no_credentials_is_a_401(self, anon_client):
        response = anon_client.get("/api/users/me")

        assert response.status_code == 401
        assert "bearer" in response.headers.get("www-authenticate", "").lower()

    def test_a_garbage_token_is_a_401(self, anon_client):
        anon_client.headers["Authorization"] = "Bearer not-a-real-token"

        assert anon_client.get("/api/users/me").status_code == 401

    def test_an_expired_token_is_a_401(self, anon_client, user):
        dead = create_access_token(user.id, expires_in=timedelta(seconds=-1))
        anon_client.headers["Authorization"] = f"Bearer {dead}"

        assert anon_client.get("/api/users/me").status_code == 401

    def test_a_token_for_a_deleted_user_is_a_401_not_a_500(self, anon_client, db, user):
        # Decoding successfully is not the same as the account still existing.
        token = create_access_token(user.id)
        db.delete(user)
        db.commit()
        anon_client.headers["Authorization"] = f"Bearer {token}"

        assert anon_client.get("/api/users/me").status_code == 401

    def test_a_token_naming_a_user_that_never_existed_is_a_401(self, anon_client):
        anon_client.headers["Authorization"] = f"Bearer {create_access_token(999_999)}"

        assert anon_client.get("/api/users/me").status_code == 401

    def test_an_empty_bearer_value_is_a_401(self, anon_client):
        anon_client.headers["Authorization"] = "Bearer "

        assert anon_client.get("/api/users/me").status_code == 401


class TestNoDevUser:
    def test_an_unauthenticated_request_does_not_conjure_an_account(self, anon_client, db):
        # The old behaviour created dev@example.com on first use. Nothing may
        # bring a user into existence just because a request arrived.
        anon_client.get("/api/users/me")

        assert db.query(User).count() == 0
