"""
Tests for the provider credential (app/api/settings.py).

This is the first thing the app stores on a *user's* behalf rather than the
deployment's, so most of what is pinned here is about not leaking it: it never
comes back out of the API, it is not readable in the table, and it belongs to
exactly one account.
"""

import pytest

from app.db.models import ProviderCredential

KEY = "not-a-real-key-for-the-suite-9f2c"


def save(client, **overrides):
    body = {"provider": "anthropic", "api_key": KEY} | overrides
    return client.put("/api/settings/provider", json=body)


class TestSaving:
    def test_a_key_can_be_saved(self, client):
        assert save(client).status_code == 200

    def test_saving_reports_it_is_configured(self, client):
        assert save(client).json()["configured"] is True

    def test_saving_again_replaces_rather_than_accumulates(self, client, db, user):
        save(client)
        save(client, provider="openai", api_key="not-a-real-key-either-4d1a")

        rows = db.query(ProviderCredential).filter_by(user_id=user.id).all()
        assert len(rows) == 1 and rows[0].provider == "openai"

    def test_an_unknown_provider_is_refused(self, client):
        assert save(client, provider="hal9000").status_code == 422

    def test_an_empty_key_is_refused(self, client):
        assert save(client, api_key="   ").status_code == 422

    def test_a_model_override_is_kept(self, client):
        assert save(client, model="claude-sonnet-5").json()["model"] == "claude-sonnet-5"

    def test_no_override_means_the_providers_default(self, client):
        from app.services.llm import PROVIDERS

        assert save(client).json()["model"] == PROVIDERS["anthropic"].default_model


class TestNotLeakingIt:
    def test_the_key_is_never_in_the_response(self, client):
        save(client)

        # The whole body, not one field: a key that leaks does not care which
        # key it leaked through.
        assert KEY not in client.get("/api/settings/provider").text

    def test_the_key_is_not_in_the_response_to_saving_it_either(self, client):
        assert KEY not in save(client).text

    def test_only_the_last_four_characters_come_back(self, client):
        save(client)

        assert client.get("/api/settings/provider").json()["key_hint"] == "9f2c"

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

        assert client.get("/api/settings/provider").json()["configured"] is False


class TestOwnership:
    def test_another_account_does_not_see_this_one_s_credential(self, client, other_client):
        save(client)

        assert other_client.get("/api/settings/provider").json()["configured"] is False

    def test_another_account_saving_does_not_disturb_this_one(self, client, other_client, db, user):
        save(client)
        save(other_client, provider="openai", api_key="not-a-real-key-somebody-else-0000")

        mine = db.query(ProviderCredential).filter_by(user_id=user.id).one()
        assert mine.provider == "anthropic"

    def test_another_account_cannot_delete_this_one_s_credential(self, client, other_client):
        save(client)
        other_client.delete("/api/settings/provider")

        assert client.get("/api/settings/provider").json()["configured"] is True

    @pytest.mark.parametrize("method,path", [("get", "/api/settings/provider"), ("delete", "/api/settings/provider")])
    def test_a_stranger_is_refused(self, anon_client, method, path):
        assert getattr(anon_client, method)(path).status_code == 401

    def test_a_stranger_cannot_save_one(self, anon_client):
        assert save(anon_client).status_code == 401


class TestForgetting:
    def test_the_key_can_be_forgotten(self, client):
        save(client)
        client.delete("/api/settings/provider")

        assert client.get("/api/settings/provider").json()["configured"] is False

    def test_forgetting_removes_the_row_rather_than_blanking_it(self, client, db, user):
        save(client)
        client.delete("/api/settings/provider")

        assert db.query(ProviderCredential).filter_by(user_id=user.id).count() == 0

    def test_forgetting_nothing_is_not_an_error(self, client):
        # Pressing it twice, or on an account that never had one.
        assert client.delete("/api/settings/provider").status_code == 204


class TestWhatTheFormNeeds:
    def test_the_offered_providers_come_back_with_the_settings(self, client):
        offered = client.get("/api/settings/provider").json()["available"]

        assert {p["id"] for p in offered} == {"anthropic", "openai"}

    def test_each_offered_provider_carries_a_label_and_a_default(self, client):
        for provider in client.get("/api/settings/provider").json()["available"]:
            assert provider["label"] and provider["default_model"]

    def test_an_account_with_no_key_is_still_told_what_it_could_pick(self, client):
        body = client.get("/api/settings/provider").json()

        assert body["configured"] is False and len(body["available"]) == 2
