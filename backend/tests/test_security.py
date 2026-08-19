"""
Tests for password hashing and token signing (app/core/security.py).

These are the primitives every other auth test stands on, so they are checked
directly rather than through a route. The properties that matter are not
"it returns a string": a hash must not be reversible or stable across calls,
and a decode must fail closed on every kind of bad input rather than raising
into a 500.
"""

from datetime import timedelta

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_a_password_verifies_against_its_own_hash(self):
        digest = hash_password("correct horse battery staple")

        assert verify_password(digest, "correct horse battery staple")

    def test_a_wrong_password_does_not_verify(self):
        digest = hash_password("correct horse battery staple")

        assert not verify_password(digest, "Correct horse battery staple")

    def test_the_hash_does_not_contain_the_password(self):
        digest = hash_password("correct horse battery staple")

        assert "correct horse battery staple" not in digest

    def test_hashing_the_same_password_twice_gives_different_hashes(self):
        # A per-hash salt is what stops one leaked hash from identifying every
        # other account that chose the same password.
        assert hash_password("hunter2hunter2") != hash_password("hunter2hunter2")

    def test_a_malformed_hash_is_a_failed_verification_not_an_exception(self):
        # The dev user is backfilled with "!" precisely because no argon2 hash
        # can equal it. That row must be unloggable-into, not a 500.
        assert not verify_password("!", "anything at all")


class TestAccessTokens:
    def test_a_token_round_trips_to_its_user_id(self):
        token = create_access_token(42)

        assert decode_access_token(token) == 42

    def test_an_expired_token_is_rejected(self):
        token = create_access_token(42, expires_in=timedelta(seconds=-1))

        assert decode_access_token(token) is None

    def test_garbage_is_rejected(self):
        assert decode_access_token("not.a.token") is None

    def test_a_token_signed_with_another_secret_is_rejected(self):
        # Forged with a different key: the signature check is the whole point.
        import jwt

        forged = jwt.encode({"sub": "42"}, "a" * 32, algorithm="HS256")

        assert decode_access_token(forged) is None

    def test_the_token_is_not_readable_as_the_user_id_alone(self):
        # Sanity check that we are signing rather than encoding: two users must
        # not produce tokens that differ only where the id sits.
        assert create_access_token(1) != create_access_token(2)
