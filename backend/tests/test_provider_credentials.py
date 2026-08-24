"""
Tests for provider credentials (app/api/settings.py).

This is the first thing the app stores on a *user's* behalf rather than the
deployment's, so most of what is pinned here is about not leaking it: it never
comes back out of the API, it is not readable in the table, and it belongs to
exactly one account.

The rest is about the bargain the settings dialog makes. A key is not stored
until it has been used — `llm.check_key` is called first, and what it returns is
both the picker's contents and the proof the credential works. Every test here
fakes that call at the call site, as tests/test_chats.py does for `llm.reply`;
no provider is ever reached.
"""

import pytest

from app.db.models import ProviderCredential, User

KEY = "not-a-real-key-for-the-suite-9f2c"
OTHER_KEY = "not-a-real-key-either-4d1a"

# What the fake provider says it can reach. Deliberately not in the registry's
# default order, so "the default was chosen" and "the first was chosen" cannot
# pass for each other.
CATALOGUE = ["some-small-model", "some-large-model"]


@pytest.fixture(autouse=True)
def catalogue(monkeypatch):
    """
    Every provider answers, unless a test says otherwise.

    Patched where it is used, not where it lives — the same shape as
    test_chats.py's fake `reply`. Autouse because a save that does not reach a
    provider is now a save that does not happen, so the alternative is this line
    at the top of nearly every test below.

    `check_key` rather than `list_models`: what it does per provider — and
    whether that is one call or two — is settled in tests/test_llm.py.
    """
    monkeypatch.setattr("app.api.settings.llm.check_key", lambda *a: list(CATALOGUE))


def save(client, provider="anthropic", api_key=KEY):
    return client.put(f"/api/settings/providers/{provider}", json={"api_key": api_key})


def settings(client):
    return client.get("/api/settings/providers").json()


def configured(client, provider):
    """The one entry for `provider`, or None."""
    return next((c for c in settings(client)["configured"] if c["provider"] == provider), None)


class TestSaving:
    def test_a_key_can_be_saved(self, client):
        assert save(client).status_code == 200

    def test_the_provider_is_listed_as_configured(self, client):
        save(client)

        assert configured(client, "anthropic") is not None

    def test_what_the_key_can_reach_is_kept(self, client):
        assert save(client).json()["configured"][0]["models"] == CATALOGUE

    def test_an_unknown_provider_is_refused(self, client):
        assert save(client, provider="hal9000").status_code == 422

    def test_an_empty_key_is_refused(self, client):
        assert save(client, api_key="   ").status_code == 422

    def test_saving_the_same_provider_again_replaces_the_row(self, client, db, user):
        save(client)
        save(client, api_key=OTHER_KEY)

        rows = db.query(ProviderCredential).filter_by(user_id=user.id).all()
        assert len(rows) == 1

    def test_saving_the_same_provider_again_keeps_the_newer_key(self, client):
        save(client)
        save(client, api_key=OTHER_KEY)

        assert configured(client, "anthropic")["key_hint"] == OTHER_KEY[-4:]


class TestKeepingSeveral:
    """
    The change this feature is: a second provider is a second row, not a
    replacement. Changing model should never cost a key you already pasted.
    """

    def test_two_providers_can_be_configured_at_once(self, client):
        save(client, provider="anthropic")
        save(client, provider="openai", api_key=OTHER_KEY)

        assert {c["provider"] for c in settings(client)["configured"]} == {
            "anthropic",
            "openai",
        }

    def test_the_earlier_key_survives_the_later_one(self, client):
        save(client, provider="anthropic")
        save(client, provider="openai", api_key=OTHER_KEY)

        assert configured(client, "anthropic")["key_hint"] == KEY[-4:]

    def test_forgetting_one_leaves_the_other(self, client):
        save(client, provider="anthropic")
        save(client, provider="openai", api_key=OTHER_KEY)
        client.delete("/api/settings/providers/anthropic")

        assert [c["provider"] for c in settings(client)["configured"]] == ["openai"]


class TestValidatingTheKey:
    """
    The reason the save is a dialog. Being told the key is wrong at the moment
    it is pasted is the difference between a mistyped character and a
    conversation that fails much later for reasons nobody can see.
    """

    def test_a_refused_key_is_a_bad_gateway(self, client, monkeypatch):
        monkeypatch.setattr("app.api.settings.llm.check_key", _refuses)

        assert save(client).status_code == 502

    def test_a_refused_key_is_not_stored(self, client, db, user, monkeypatch):
        monkeypatch.setattr("app.api.settings.llm.check_key", _refuses)
        save(client)

        assert db.query(ProviderCredential).filter_by(user_id=user.id).count() == 0

    def test_a_refused_key_does_not_become_the_active_one(self, client, monkeypatch):
        monkeypatch.setattr("app.api.settings.llm.check_key", _refuses)
        save(client)

        assert settings(client)["active"] is None

    def test_the_providers_own_words_come_back(self, client, monkeypatch):
        monkeypatch.setattr("app.api.settings.llm.check_key", _refuses)

        # The only thing that tells a wrong key apart from a spent quota.
        assert "Incorrect API key" in save(client).json()["detail"]

    def test_the_key_is_not_quoted_back_in_the_refusal(self, client, monkeypatch):
        """
        Providers do echo the offending key in an authentication error, and that
        message is on its way to the screen and into any log of the response.
        """
        monkeypatch.setattr(
            "app.api.settings.llm.check_key",
            lambda provider, api_key: _refuses(provider, api_key, quoting=True),
        )

        assert KEY not in save(client).text

    def test_a_replacement_that_fails_leaves_the_working_key_alone(self, client, monkeypatch):
        save(client)
        monkeypatch.setattr("app.api.settings.llm.check_key", _refuses)
        save(client, api_key=OTHER_KEY)

        assert configured(client, "anthropic")["key_hint"] == KEY[-4:]


class TestChoosingAModel:
    def test_the_first_key_saved_becomes_the_active_provider(self, client):
        save(client)

        assert settings(client)["active"]["provider"] == "anthropic"

    def test_a_later_key_does_not_take_over_the_active_choice(self, client):
        save(client, provider="anthropic")
        save(client, provider="openai", api_key=OTHER_KEY)

        assert settings(client)["active"]["provider"] == "anthropic"

    def test_the_active_model_falls_to_something_the_key_can_reach(self, client):
        """
        The registry's default is a guess written months ago. If the provider
        has never heard of it, the first chat would fail on a model name — so
        the catalogue wins over the default.
        """
        save(client)

        assert settings(client)["active"]["model"] in CATALOGUE

    def test_the_registry_default_is_preferred_when_it_is_offered(self, client, monkeypatch):
        from app.services.llm import PROVIDERS

        default = PROVIDERS["anthropic"].default_model
        monkeypatch.setattr("app.api.settings.llm.check_key", lambda *a: ["z-model", default])
        save(client)

        assert settings(client)["active"]["model"] == default

    def test_a_model_can_be_chosen(self, client):
        save(client)
        chosen = {"provider": "anthropic", "model": CATALOGUE[1]}

        assert client.put("/api/settings/active-model", json=chosen).status_code == 200

    def test_the_choice_sticks(self, client):
        save(client)
        client.put(
            "/api/settings/active-model",
            json={"provider": "anthropic", "model": CATALOGUE[1]},
        )

        assert settings(client)["active"]["model"] == CATALOGUE[1]

    def test_switching_provider_switches_the_key_used(self, client, db, user):
        save(client, provider="anthropic")
        save(client, provider="openai", api_key=OTHER_KEY)
        client.put(
            "/api/settings/active-model",
            json={"provider": "openai", "model": CATALOGUE[0]},
        )

        assert db.get(User, user.id).active_provider == "openai"

    def test_a_provider_with_no_key_cannot_be_chosen(self, client):
        save(client, provider="anthropic")

        assert (
            client.put(
                "/api/settings/active-model",
                json={"provider": "openai", "model": CATALOGUE[0]},
            ).status_code
            == 409
        )

    def test_a_model_the_provider_never_listed_is_refused(self, client):
        # Not pedantry: it is a typo or a stale tab, and the alternative is a
        # chat that fails on the model name with no way back to a working one.
        save(client)

        assert (
            client.put(
                "/api/settings/active-model",
                json={"provider": "anthropic", "model": "no-such-model"},
            ).status_code
            == 422
        )


class TestRefreshing:
    def test_the_list_can_be_refreshed(self, client, monkeypatch):
        save(client)
        monkeypatch.setattr("app.api.settings.llm.check_key", lambda *a: ["a-new-model"])
        client.post("/api/settings/providers/anthropic/refresh")

        assert configured(client, "anthropic")["models"] == ["a-new-model"]

    def test_refreshing_reuses_the_stored_key(self, client, monkeypatch):
        save(client)
        seen = {}
        monkeypatch.setattr(
            "app.api.settings.llm.check_key",
            lambda provider, api_key: seen.setdefault("key", api_key) and CATALOGUE,
        )
        client.post("/api/settings/providers/anthropic/refresh")

        assert seen["key"] == KEY

    def test_refreshing_a_provider_with_no_key_is_refused(self, client):
        assert client.post("/api/settings/providers/openai/refresh").status_code == 409

    def test_refreshing_a_provider_that_has_left_the_registry_is_refused(self, client, monkeypatch):
        """
        A key stored under a provider this build no longer has. The row is real
        and the reader can still see and forget it, so this is a refusal rather
        than the 500 an unhandled UnknownProvider would be.
        """
        save(client)
        monkeypatch.setattr("app.api.settings.llm.check_key", _vanished)

        assert client.post("/api/settings/providers/anthropic/refresh").status_code == 409

    def test_a_refresh_that_drops_the_active_model_moves_it(self, client, monkeypatch):
        """
        A model can be retired between one visit and the next. Leaving the
        account pointed at it would make every chat fail with nothing on screen
        explaining why.
        """
        save(client)
        monkeypatch.setattr("app.api.settings.llm.check_key", lambda *a: ["a-new-model"])
        client.post("/api/settings/providers/anthropic/refresh")

        assert settings(client)["active"]["model"] == "a-new-model"


class TestNotLeakingIt:
    def test_the_key_is_never_in_the_response(self, client):
        save(client)

        # The whole body, not one field: a key that leaks does not care which
        # key it leaked through.
        assert KEY not in client.get("/api/settings/providers").text

    def test_the_key_is_not_in_the_response_to_saving_it_either(self, client):
        assert KEY not in save(client).text

    def test_only_the_last_four_characters_come_back(self, client):
        save(client)

        assert configured(client, "anthropic")["key_hint"] == "9f2c"

    def test_the_stored_column_is_not_the_key(self, client, db, user):
        save(client)

        stored = db.query(ProviderCredential).filter_by(user_id=user.id).one()
        assert KEY not in stored.api_key_encrypted

    def test_a_key_this_deployment_cannot_read_reads_as_absent(self, client, db, user):
        """
        The JWT_SECRET rotation case. The row survives and cannot be decrypted,
        and the reader has to be told to paste it again rather than shown a 500.
        """
        save(client)
        db.query(ProviderCredential).filter_by(user_id=user.id).one().api_key_encrypted = (
            "gAAAAA-written-under-some-other-secret"
        )
        db.commit()

        assert settings(client)["configured"] == []


class TestOwnership:
    def test_another_account_does_not_see_this_one_s_credential(self, client, other_client):
        save(client)

        assert settings(other_client)["configured"] == []

    def test_another_account_does_not_inherit_the_active_choice(self, client, other_client):
        save(client)

        assert settings(other_client)["active"] is None

    def test_another_account_saving_does_not_disturb_this_one(self, client, other_client):
        save(client)
        save(other_client, provider="anthropic", api_key="not-a-real-key-somebody-else-0000")

        assert configured(client, "anthropic")["key_hint"] == KEY[-4:]

    def test_another_account_cannot_delete_this_one_s_credential(self, client, other_client):
        save(client)
        other_client.delete("/api/settings/providers/anthropic")

        assert configured(client, "anthropic") is not None

    @pytest.mark.parametrize(
        "method,path",
        [
            ("get", "/api/settings/providers"),
            ("delete", "/api/settings/providers/anthropic"),
            ("post", "/api/settings/providers/anthropic/refresh"),
        ],
    )
    def test_a_stranger_is_refused(self, anon_client, method, path):
        assert getattr(anon_client, method)(path).status_code == 401

    def test_a_stranger_cannot_save_one(self, anon_client):
        assert save(anon_client).status_code == 401


class TestForgetting:
    def test_the_key_can_be_forgotten(self, client):
        save(client)
        client.delete("/api/settings/providers/anthropic")

        assert configured(client, "anthropic") is None

    def test_forgetting_removes_the_row_rather_than_blanking_it(self, client, db, user):
        save(client)
        client.delete("/api/settings/providers/anthropic")

        assert db.query(ProviderCredential).filter_by(user_id=user.id).count() == 0

    def test_forgetting_the_active_provider_clears_the_choice(self, client):
        save(client)
        client.delete("/api/settings/providers/anthropic")

        assert settings(client)["active"] is None

    def test_forgetting_the_active_provider_falls_back_to_another(self, client):
        # Otherwise removing one of two keys leaves an account that has a
        # working credential and still refuses to chat.
        save(client, provider="anthropic")
        save(client, provider="openai", api_key=OTHER_KEY)
        client.delete("/api/settings/providers/anthropic")

        assert settings(client)["active"]["provider"] == "openai"

    def test_forgetting_nothing_is_not_an_error(self, client):
        # Pressing it twice, or on an account that never had one.
        assert client.delete("/api/settings/providers/anthropic").status_code == 204


class TestWhatTheDialogNeeds:
    def test_every_provider_in_the_registry_is_offered(self, client):
        """
        The dialog is built from this list, so a provider missing here is one
        nobody can add a key for. Compared against the registry itself rather
        than a copy of it: the copy is what goes stale, and what it would fail
        to catch is a route that quietly drops a row.
        """
        from app.services.llm import PROVIDERS

        offered = settings(client)["available"]

        assert {p["id"] for p in offered} == set(PROVIDERS)

    def test_each_offered_provider_carries_a_label_and_a_default(self, client):
        for provider in settings(client)["available"]:
            assert provider["label"] and provider["default_model"]

    def test_an_account_with_no_key_is_still_told_what_it_could_pick(self, client):
        from app.services.llm import PROVIDERS

        body = settings(client)

        assert body["configured"] == [] and len(body["available"]) == len(PROVIDERS)


def _vanished(provider, api_key):
    """A provider that is no longer in the registry."""
    from app.services.llm import UnknownProvider

    raise UnknownProvider(f"Unknown provider: {provider}")


def _refuses(provider, api_key, quoting=False):
    """A provider that will not answer, optionally quoting the key back."""
    from app.services.llm import ProviderError

    quoted = f" (key {api_key})" if quoting else ""
    raise ProviderError(f"401 Incorrect API key provided{quoted}")
