"""
Tests for the conversation summary (app/services/conversation_summary.py).

The model is never called. What is pinned is the shape of the request and the
shape of the refusal: the transcript has to say who said what, and a provider
that will not answer has to leave the chat summarisable later rather than
half-written.

The summary used to be four fields, two of which were about the reader by
construction — "the main focus of the reader's questions". It is prose and a
list of actions now, because that is what a student watching a discussion would
actually write down, and because nothing in the interface ever read the four
fields: the frontend redirects to the note, and the note holds the prose.
"""

import pytest

from app.services import conversation_summary as summary

TURNS = [
    ("user", "how do I stop mixing up affect and effect?"),
    ("assistant", "affect is usually the verb, effect usually the noun."),
    ("user", "what about 'effect change'?"),
    ("assistant", "that is the rarer verb sense of effect, meaning to bring about."),
]

ANSWER = summary.ConversationSummary(
    title="Affect and effect",
    notes="Affect is usually the verb and effect usually the noun. Effect has a "
    "rarer verb sense meaning to bring about, as in 'effect change'.",
    actions=["Reread anything written this week for the two words."],
)


class TestTheTranscriptItSends:
    """
    Unchanged by the reshaping, and deliberately so.

    Notes that cannot tell a question from an answer read as mush, so the
    labelling still earns its place even though nothing downstream is organised
    around the two sides any more.
    """

    def test_it_names_the_note_a_conversation_started_from(self):
        """
        A summariser that has not seen the note describes the replies without
        knowing what they were replying about — and for a chat opened from a
        note, that context is often the only statement of the subject.
        """
        text = summary.transcript([("system", "The moon pulls."), *TURNS])

        assert "From your note: The moon pulls." in text

    def test_it_labels_both_speakers(self):
        transcript = summary.transcript(TURNS)

        assert "affect and effect" in transcript
        assert transcript.count("You:") == 2
        assert transcript.count("Assistant:") == 2

    def test_it_keeps_the_turns_in_order(self):
        transcript = summary.transcript(TURNS)

        assert transcript.index("affect and effect") < transcript.index("effect change")

    def test_an_unknown_role_is_refused(self):
        with pytest.raises(ValueError):
            summary.transcript([("narrator", "meanwhile")])


class TestTheInstruction:
    """
    The prompt is an instruction to a model, not a guarantee, so this is the
    honest limit of what a test can do: it pins that the rule is still being
    asked for. Whether the model obeys is checked by reading a real summary.
    """

    def test_it_forbids_describing_the_reader(self):
        # The failure this exists to prevent: "the user strongly disagreed with
        # the answer." Two of the four old fields invited exactly that.
        assert "never describe the reader" in summary.INSTRUCTION.lower()

    def test_it_asks_for_actions_only_when_there_are_any(self):
        assert "empty" in summary.INSTRUCTION.lower()


class TestTheAnswer:
    def test_it_returns_the_prose_and_the_actions(self, monkeypatch):
        _answering(monkeypatch, ANSWER)

        got = summary.summarize("anthropic", "k", None, TURNS)

        assert got.notes == ANSWER.notes
        assert got.actions == ANSWER.actions
        assert got.title == ANSWER.title

    def test_it_asks_for_the_schema_it_wants_back(self, monkeypatch):
        asked = {}

        class Model:
            def with_structured_output(self, schema):
                asked["schema"] = schema
                return _Invoker(ANSWER)

        monkeypatch.setattr(summary.llm, "chat_model", lambda *a: Model())
        summary.summarize("anthropic", "k", None, TURNS)

        assert asked["schema"] is summary.ConversationSummary

    def test_a_dict_answer_is_coerced(self, monkeypatch):
        # Not every integration returns the pydantic object; some hand back the
        # parsed dict. Both have to end up as one type at the call site.
        _answering(monkeypatch, ANSWER.model_dump())

        assert summary.summarize("anthropic", "k", None, TURNS).notes == ANSWER.notes

    def test_no_actions_is_a_summary_rather_than_a_failure(self, monkeypatch):
        # A conversation that implies nothing to do is the ordinary case, not a
        # partial answer — so an empty list has to validate.
        _answering(monkeypatch, {"title": "T", "notes": "Some prose.", "actions": []})

        assert summary.summarize("anthropic", "k", None, TURNS).actions == []


class TestWhenItCannot:
    def test_a_provider_failure_answers_none(self, monkeypatch):
        """
        None rather than an exception, the same contract as ranker.py: the
        route turns it into a refusal the reader can retry, and the transcript
        is untouched.
        """

        class Model:
            def with_structured_output(self, schema):
                raise RuntimeError("503 model overloaded")

        monkeypatch.setattr(summary.llm, "chat_model", lambda *a: Model())

        assert summary.summarize("anthropic", "k", None, TURNS) is None

    def test_an_unusable_answer_is_none_rather_than_a_half_summary(self, monkeypatch):
        _answering(monkeypatch, {"notes": "prose with no title"})

        assert summary.summarize("anthropic", "k", None, TURNS) is None

    def test_an_empty_conversation_has_nothing_to_summarise(self, monkeypatch):
        _answering(monkeypatch, ANSWER)

        assert summary.summarize("anthropic", "k", None, []) is None


class _Invoker:
    def __init__(self, answer):
        self.answer = answer

    def invoke(self, messages):
        return self.answer


def _answering(monkeypatch, answer):
    """A chat model whose structured output is `answer`."""

    class Model:
        def with_structured_output(self, schema):
            return _Invoker(answer)

    monkeypatch.setattr(summary.llm, "chat_model", lambda *a: Model())


class TestAsNote:
    """
    The summary, rendered as the text of a note.

    Real markdown now. The note renders markdown at rest as of PR #52, so the
    heading below is a `##` rather than the line-with-a-blank-line-under-it the
    old version had to settle for.
    """

    def _summary(self, **over):
        base = dict(
            title="Gerunds",
            notes="A gerund is a verb form ending in -ing that works as a noun.",
            actions=["Find three gerunds in your own writing."],
        )
        base.update(over)
        return summary.ConversationSummary(**base)

    def test_the_prose_comes_first_with_nothing_above_it(self):
        # No "What this was about" heading over it any more. The note opens on
        # the notes themselves, which is what a page of notes looks like.
        text = summary.as_note(self._summary())

        assert text.startswith("A gerund is a verb form")

    def test_the_actions_are_a_markdown_list_under_a_heading(self):
        text = summary.as_note(self._summary())

        assert "## " in text
        assert "- Find three gerunds in your own writing." in text

    def test_every_action_gets_its_own_bullet(self):
        text = summary.as_note(self._summary(actions=["First thing", "Second thing"]))

        assert "- First thing" in text
        assert "- Second thing" in text

    def test_no_heading_at_all_when_there_is_nothing_to_do(self):
        # An empty heading would be the note claiming a section it does not
        # have — and most conversations imply no actions.
        text = summary.as_note(self._summary(actions=[]))

        assert "#" not in text
        assert text == "A gerund is a verb form ending in -ing that works as a noun."

    def test_the_title_is_not_written_into_the_body(self):
        """It is the note's title; repeating it as a heading says it twice."""
        text = summary.as_note(self._summary(title="Gerunds"))

        assert "Gerunds" not in text
