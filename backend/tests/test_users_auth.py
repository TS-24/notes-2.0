"""
Tests that an account can only act on itself (app/api/users.py).

The routes here used to take a user id from the path and never compare it to
the caller, so any account could rename or delete any other. Two of them are
gone entirely rather than guarded: listing every user has no caller now that
there is no admin role, and creating one bypassed the invite that registration
exists to enforce.
"""

from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import User


class TestSelf:
    def test_me_is_the_signed_in_account(self, client, user):
        response = client.get("/api/users/me")

        assert response.status_code == 200
        assert response.json()["email"] == user.email

    def test_the_hash_is_never_in_the_response(self, client):
        body = client.get("/api/users/me").text

        assert "password" not in body
        assert "argon2" not in body

    def test_i_can_rename_myself(self, client, db, user):
        response = client.patch("/api/users/me", json={"username": "renamed"})

        assert response.status_code == 200
        db.expire_all()
        assert db.get(User, user.id).username == "renamed"

    def test_i_can_delete_myself(self, client, db, user):
        response = client.delete("/api/users/me")

        assert response.status_code == 204
        assert db.get(User, user.id) is None

    def test_an_account_that_used_an_invite_can_still_be_deleted(self, client, db, user):
        """
        Registration leaves invite_codes.used_by_user_id pointing at the new
        account, and that reference outlives nothing on its own. Without the
        relationship it is a foreign key violation — a 500 on the delete — for
        every account that came through the front door. The fixtures build
        users directly, so only a test that redeems a code the way registration
        does can catch it.
        """
        from app.db.models import InviteCode

        db.add(InviteCode(code="spent", used_at=datetime.now(timezone.utc), used_by_user_id=user.id))
        db.commit()

        response = client.delete("/api/users/me")

        assert response.status_code == 204
        # The code stays, still marked spent; only the pointer to the account
        # goes. It is a record that the invite was used, not a part of the user.
        remaining = db.scalars(select(InviteCode)).one()
        assert remaining.used_at is not None
        assert remaining.used_by_user_id is None

    def test_i_cannot_read_another_account(self, client, other_user):
        assert client.get(f"/api/users/{other_user.id}").status_code in (404, 405)

    def test_i_cannot_rename_another_account(self, client, db, other_user):
        response = client.patch(
            f"/api/users/{other_user.id}", json={"username": "hijacked"}
        )

        assert response.status_code in (404, 405)
        db.expire_all()
        assert db.get(User, other_user.id).username != "hijacked"

    def test_i_cannot_delete_another_account(self, client, db, other_user):
        response = client.delete(f"/api/users/{other_user.id}")

        assert response.status_code in (404, 405)
        assert db.get(User, other_user.id) is not None

    def test_the_roster_of_every_account_is_gone(self, client):
        # It listed every registered email to anyone who asked.
        assert client.get("/api/users").status_code in (404, 405)

    def test_open_user_creation_is_gone(self, anon_client):
        # It sat next to invite-only registration and ignored the invite.
        response = anon_client.post(
            "/api/users", json={"username": "sneak", "email": "sneak@example.com"}
        )

        assert response.status_code in (404, 405)


class TestWithoutCredentials:
    def test_me_refuses(self, anon_client):
        assert anon_client.get("/api/users/me").status_code == 401

    def test_patching_me_refuses(self, anon_client):
        assert anon_client.patch("/api/users/me", json={"username": "x"}).status_code == 401

    def test_deleting_me_refuses(self, anon_client):
        assert anon_client.delete("/api/users/me").status_code == 401
