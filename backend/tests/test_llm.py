"""
Tests for the LangChain provider layer (app/services/llm.py).

No provider is ever called here. What matters is not whether a model gives good
answers — that is not a judgement a test can make — but that the registry names
real classes, that a transcript is converted into the message types LangChain
expects, and that a provider failure arrives as one recognisable exception
rather than as whichever SDK error happened to escape.
"""

import pytest

from app.services import llm

TURNS = [("user", "what is a gerund?"), ("assistant", "a verb acting as a noun")]


class TestRegistry:
    def test_both_providers_are_offered(self):
        assert set(llm.PROVIDERS) == {"anthropic", "openai"}

    @pytest.mark.parametrize("provider", ["anthropic", "openai"])
    def test_every_provider_names_an_importable_class(self, provider):
        """
        The registry is a table of import paths, so a typo in it is invisible
        until someone with a key tries to chat. This is the check that a
        renamed class is caught here instead.
        """
        assert llm.provider_class(provider) is not None

    @pytest.mark.parametrize("provider", ["anthropic", "openai"])
    def test_every_provider_has_a_default_model(self, provider):
        assert llm.PROVIDERS[provider].default_model

    def test_an_unknown_provider_is_refused(self):
        with pytest.raises(llm.UnknownProvider):
            llm.chat_model("hal9000", "k", None)

    def test_the_default_model_is_used_when_none_is_given(self, monkeypatch):
        built = {}

        def fake(provider):
            def cls(**kwargs):
                built.update(kwargs)
                return object()

            return cls

        monkeypatch.setattr(llm, "provider_class", fake)
        llm.chat_model("anthropic", "secret-key", None)

        assert built["model"] == llm.PROVIDERS["anthropic"].default_model

    def test_the_call_is_given_a_timeout(self, monkeypatch):
        """
        Every chat route is a sync `def`, so it runs in FastAPI's threadpool. A
        provider that accepts the connection and then stalls holds that slot for
        as long as the SDK's own default allows, and enough of those stop the
        app serving anything at all.
        """
        built = {}

        def fake(provider):
            def cls(**kwargs):
                built.update(kwargs)
                return object()

            return cls

        monkeypatch.setattr(llm, "provider_class", fake)
        llm.chat_model("anthropic", "secret-key", None)

        assert built["timeout"] == llm.TIMEOUT_SECONDS
        assert built["max_retries"] == llm.MAX_RETRIES

    def test_an_explicit_model_overrides_the_default(self, monkeypatch):
        built = {}

        def fake(provider):
            def cls(**kwargs):
                built.update(kwargs)
                return object()

            return cls

        monkeypatch.setattr(llm, "provider_class", fake)
        llm.chat_model("openai", "secret-key", "some-other-model")

        assert built["model"] == "some-other-model"


class TestTranscriptConversion:
    def test_the_system_prompt_leads(self):
        from langchain_core.messages import SystemMessage

        assert isinstance(llm.to_messages(TURNS)[0], SystemMessage)

    def test_roles_map_to_their_message_types(self):
        from langchain_core.messages import AIMessage, HumanMessage

        human, ai = llm.to_messages(TURNS)[1:]

        assert isinstance(human, HumanMessage) and human.content == TURNS[0][1]
        assert isinstance(ai, AIMessage) and ai.content == TURNS[1][1]

    def test_an_empty_transcript_is_still_addressable(self):
        # Only the system message; a chat with no turns is not an error.
        assert len(llm.to_messages([])) == 1

    def test_an_unknown_role_is_refused(self):
        # A role the database should never hold. Guessing at it would put words
        # in one speaker's mouth as the other's.
        with pytest.raises(ValueError):
            llm.to_messages([("narrator", "meanwhile")])


class TestReply:
    def test_it_returns_the_models_text(self, monkeypatch):
        monkeypatch.setattr(llm, "chat_model", lambda *a: _stub("a verb acting as a noun"))

        assert llm.reply("anthropic", "k", None, TURNS) == "a verb acting as a noun"

    def test_content_arriving_in_blocks_is_flattened(self, monkeypatch):
        """
        A chat model may answer with a list of content blocks rather than a
        string. Storing the repr of a list is the kind of thing that only shows
        up on screen, so it is settled here.
        """
        monkeypatch.setattr(
            llm,
            "chat_model",
            lambda *a: _stub([{"type": "text", "text": "a verb "}, {"type": "text", "text": "as a noun"}]),
        )

        assert llm.reply("anthropic", "k", None, TURNS) == "a verb as a noun"

    def test_a_provider_failure_becomes_one_exception(self, monkeypatch):
        """
        Anthropic and OpenAI raise entirely different types for the same "your
        key is wrong". The route above cannot branch on both, so they arrive
        here as one.
        """

        def explode(*_):
            raise RuntimeError("401 invalid x-api-key")

        monkeypatch.setattr(llm, "chat_model", lambda *a: _stub(raises=explode))

        with pytest.raises(llm.ProviderError) as caught:
            llm.reply("anthropic", "k", None, TURNS)

        # The provider's own words, because they are the only thing that says
        # which of the many ways this can fail actually happened.
        assert "invalid x-api-key" in str(caught.value)

    def test_an_empty_answer_is_refused(self, monkeypatch):
        # Storing an empty assistant turn leaves a chat that looks broken and a
        # transcript the summary would have to describe as nothing.
        monkeypatch.setattr(llm, "chat_model", lambda *a: _stub("   "))

        with pytest.raises(llm.ProviderError):
            llm.reply("anthropic", "k", None, TURNS)


def _stub(content: object = "", raises=None):
    """A chat model that answers with `content`, or fails."""

    class Stub:
        def invoke(self, messages):
            if raises is not None:
                raises(messages)
            return type("Response", (), {"content": content})()

    return Stub()
