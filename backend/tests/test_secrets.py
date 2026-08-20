"""
Tests for credential encryption (app/core/secrets.py).

What is pinned here is the contract, not the cipher: a value comes back out
unchanged, it is not readable in the database, and a value this deployment
cannot decrypt reads as absent rather than blowing up. That last one is the
whole reason this module returns None instead of raising — rotating JWT_SECRET
is a supported act, and it orphans every stored key.
"""

import pytest

from app.core import secrets

KEY = "not-a-real-key-for-the-suite"


class TestRoundTrip:
    def test_a_value_survives_the_round_trip(self):
        assert secrets.decrypt(secrets.encrypt(KEY)) == KEY

    def test_the_stored_form_does_not_contain_the_key(self):
        # The point of the exercise: someone reading the table learns nothing.
        assert KEY not in secrets.encrypt(KEY)

    def test_the_same_key_encrypts_differently_every_time(self):
        # Equal ciphertexts would let a reader of the table tell which accounts
        # share a key without decrypting anything.
        assert secrets.encrypt(KEY) != secrets.encrypt(KEY)

    def test_unicode_survives(self):
        # Nothing stops a provider issuing a key we did not anticipate.
        assert secrets.decrypt(secrets.encrypt("clé-🔑")) == "clé-🔑"


class TestFailingClosed:
    def test_a_value_from_another_secret_reads_as_absent(self):
        """
        The JWT_SECRET rotation case, which is the one that will actually
        happen: the row is intact and undecryptable, and the caller has to see
        "no credential" so it can ask for the key again.
        """
        foreign = secrets.fernet_for("a-completely-different-secret-key!!").encrypt(
            KEY.encode()
        )

        assert secrets.decrypt(foreign.decode()) is None

    @pytest.mark.parametrize(
        "stored", ["", "not-a-token", "Z" * 120, "gAAAAA-almost-but-not-quite"]
    )
    def test_nothing_unparseable_raises(self, stored):
        assert secrets.decrypt(stored) is None


class TestDerivation:
    def test_the_encryption_key_is_not_the_signing_secret(self):
        """
        Both come from JWT_SECRET, and they must not be the same bytes: a token
        signature and a stored credential should not share key material just
        because they share a root.
        """
        from app.core.config import JWT_SECRET

        assert secrets.derive_key(JWT_SECRET) != JWT_SECRET.encode()

    def test_derivation_is_stable(self):
        # It has to be, or every restart orphans every credential.
        assert secrets.derive_key("some-secret") == secrets.derive_key("some-secret")

    def test_different_secrets_derive_different_keys(self):
        assert secrets.derive_key("secret-one") != secrets.derive_key("secret-two")
