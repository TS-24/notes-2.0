"""
What a finished conversation was about: notes, and anything to do.

A chat is a long thing you will not reread. What survives it is what a student
watching a discussion would actually write down — flowing prose about the
subject, and a short list of things to go and do if the conversation implied
any. The summary is written once, when the chat is finished, and it becomes the
text of the note the conversation is bound to.

It used to be four fields: general, topics, questions, answers. Two of those
were about the reader by construction — "the main focus of the reader's
questions" — which invites the one sentence this must never produce: *the user
strongly disagreed with the answer.* Notes are about the subject, not about the
person taking them. The structure also bought nothing: no part of the interface
ever read the four fields, because finishing redirects to the note and the note
holds the prose.

The shape comes back through `with_structured_output`, which is the one place
LangChain genuinely earns its keep here: it turns each provider's tool-calling
into the same typed object, so Anthropic and OpenAI need no separate parsing and
there is no JSON to coax out of prose.

Every failure returns None, the same contract as `ranker.py`. A chat that could
not be summarised keeps its transcript and can be finished again later.
"""

from typing import Sequence

from pydantic import BaseModel, Field, ValidationError

from . import llm

# The heading the actions go under, when there are any.
ACTIONS_HEADING = "What to do"

INSTRUCTION = (
    "Below is a finished conversation between a reader and an assistant. "
    "Give it a short title, then write it up as notes.\n\n"
    "Write the way a student takes notes on a discussion they watched: "
    "flowing paragraphs about the subject matter, concise but specific, "
    "covering everything that was actually established. Not a description of "
    "the conversation, and not a continuation of it — the notes should be "
    "useful to someone who never saw it.\n\n"
    "Never describe the reader or the way they wrote. No remarks about their "
    "tone, their agreement or disagreement, their confusion, their persistence, "
    "or how many times they asked something. Write about the subject only.\n\n"
    "Then list anything the reader should go and do as a result. Only real "
    "actions that follow from what was said; leave the list empty if the "
    "conversation implies none, which is the usual case."
)


class ConversationSummary(BaseModel):
    """What comes back. Field docs are the prompt the provider actually sees."""

    title: str = Field(
        description="A short name for the conversation, five words at most."
    )
    notes: str = Field(
        description=(
            "The subject matter written up as notes: flowing paragraphs, "
            "concise, specific, and comprehensive, the way a student would "
            "take notes on a discussion they watched. Never describe the "
            "reader or how they wrote."
        )
    )
    actions: list[str] = Field(
        description=(
            "Things the reader should go and do as a result of this "
            "conversation, one per item. Empty when it implies none, which is "
            "the usual case — do not invent an action to fill the list."
        )
    )


def transcript(turns: Sequence[tuple[str, str]]) -> str:
    """The conversation with its speakers named, in order.

    The labelling survived the reshaping even though nothing downstream is
    organised around the two sides any more: notes written from a block of text
    that cannot tell a question from an answer read as mush.
    """
    lines = []
    for role, content in turns:
        if role == "user":
            lines.append(f"You: {content}")
        elif role == "assistant":
            lines.append(f"Assistant: {content}")
        elif role == "system":
            # What the conversation was started from — the note it belongs to.
            # Labelled rather than dropped: it is often the only statement of
            # the subject, and a summary that has not seen it describes the
            # replies without knowing what they were replying about.
            lines.append(f"From your note: {content}")
        else:
            raise ValueError(f"Unknown role: {role}")
    return "\n\n".join(lines)


def summarize(
    provider: str, api_key: str, model: str | None, turns: Sequence[tuple[str, str]]
) -> ConversationSummary | None:
    """The summary, or None when it cannot be had.

    None rather than an exception so a provider having a bad minute costs the
    summary and not the conversation: the route refuses, and finishing the chat
    can be tried again.
    """
    if not turns:
        return None

    try:
        structured = llm.chat_model(provider, api_key, model).with_structured_output(
            ConversationSummary
        )
        answer = structured.invoke(f"{INSTRUCTION}\n\n{transcript(turns)}")
    except Exception:
        # No key, no network, a refusal, a model that cannot do tool calls —
        # all the same answer, because the remedy is the same: try later.
        return None

    if isinstance(answer, ConversationSummary):
        return answer
    # Some integrations hand back the parsed dict rather than the model. A
    # partial one is not a summary, so it fails the same way a refusal does.
    # An *empty actions list* is not partial — it is the common answer.
    try:
        return ConversationSummary.model_validate(answer)
    except (ValidationError, TypeError):
        return None


def as_note(summary: ConversationSummary) -> str:
    """
    The summary as the text of a note.

    The notes come first with nothing above them: a page of notes opens on the
    notes, and a heading reading "What this was about" over the only prose in
    the document is a label for something that needs none.

    Real markdown, unlike the version this replaces. The note renders markdown
    at rest (PR #52), so `##` and `-` arrive as a heading and a list rather than
    as punctuation the reader has to look past.

    The title is not written into the body. It is the note's title; putting it
    here as well says it twice.
    """
    if not summary.actions:
        return summary.notes

    bullets = "\n".join(f"- {action}" for action in summary.actions)
    return f"{summary.notes}\n\n## {ACTIONS_HEADING}\n\n{bullets}"
