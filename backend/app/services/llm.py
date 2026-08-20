"""
The chat itself — LangChain, talking to whichever provider the reader configured.

Unlike the word ladder's ranker, which calls a hosted model with the
deployment's own token, everything here runs on a credential the reader supplied
on /settings. So the provider is data, not a deployment decision, and this
module's job is to turn a row in `provider_credentials` plus a transcript into
one reply.

Two design notes:

**A registry, not `init_chat_model`.** LangChain will resolve a provider from a
string, but a table of import paths is greppable, fails at the point of the typo
rather than at the first request with a real key, and can be checked by a test
that has no credentials — which is the only kind of test this can have. Adding a
provider is one row here plus one package in requirements.txt.

**One exception out.** Anthropic and OpenAI raise entirely unrelated types for
the same "your key is wrong", and the route above cannot branch on both. They
leave here as `ProviderError`, carrying the provider's own words, because those
words are the only thing that distinguishes a bad key from a rate limit from a
model name that does not exist.

The provider packages are imported lazily, like `ranker._client`, so an install
where nobody ever chats never pays for them.
"""

from dataclasses import dataclass
from importlib import import_module
from typing import Sequence

# What the assistant is, in the app it lives in. Deliberately short: a long
# persona would be a prompt to maintain, and this one exists only so the model
# knows it is answering inside a notes app rather than nowhere in particular.
SYSTEM_PROMPT = (
    "You are a thoughtful companion inside a personal notes and vocabulary app. "
    "Answer plainly and concretely, in prose rather than bullet lists unless a "
    "list is genuinely the clearer form. Prefer a short precise answer to a long "
    "hedged one, and say when you are unsure."
)


# A stalled provider is worse here than a slow one. The chat routes are sync
# `def`, so each in-flight call holds a FastAPI threadpool slot, and the slot is
# shared with every other route in the app. Generous enough for a long
# summarisation, short enough that a hung provider cannot take the app down.
TIMEOUT_SECONDS = 60.0

# One retry past the first attempt. The SDK defaults retry more than this, which
# multiplies the worst case by the timeout above; a reader watching a spinner
# would rather be told it failed.
MAX_RETRIES = 1


class UnknownProvider(ValueError):
    """A provider name that is not in the registry."""


class ProviderError(RuntimeError):
    """The provider was reached and would not answer — bad key, limit, model."""


@dataclass(frozen=True)
class Provider:
    """One row of the registry: where the class lives and what to call by default."""

    label: str
    module: str
    class_name: str
    default_model: str


# Both classes take `api_key`, `model`, `timeout` and `max_retries` — verified
# against langchain-anthropic and langchain-openai 1.6.0, where several are
# aliases on the real field (`anthropic_api_key`, `model_name`, and on Anthropic
# `default_request_timeout`). That is what lets `chat_model` below be one code
# path rather than a per-provider keyword mapping.
PROVIDERS: dict[str, Provider] = {
    "anthropic": Provider(
        label="Anthropic",
        module="langchain_anthropic",
        class_name="ChatAnthropic",
        default_model="claude-opus-5",
    ),
    "openai": Provider(
        label="OpenAI",
        module="langchain_openai",
        class_name="ChatOpenAI",
        # Editable on /settings on purpose. Model names move faster than this
        # file does, and a stale default should cost one field rather than the
        # whole feature.
        default_model="gpt-5.1",
    ),
}


def provider_class(provider: str):
    """The chat model class for a provider, imported on first use."""
    known = PROVIDERS.get(provider)
    if known is None:
        raise UnknownProvider(f"Unknown provider: {provider}")
    return getattr(import_module(known.module), known.class_name)


def chat_model(provider: str, api_key: str, model: str | None):
    """A configured chat model. The reader's key, never the environment's."""
    if provider not in PROVIDERS:
        raise UnknownProvider(f"Unknown provider: {provider}")
    return provider_class(provider)(
        model=model or PROVIDERS[provider].default_model,
        api_key=api_key,
        timeout=TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
    )


def to_messages(turns: Sequence[tuple[str, str]]):
    """A stored transcript as LangChain messages, system prompt first.

    Takes role/content pairs rather than ORM rows so it stays a pure function
    with nothing to set up — the route unpacks `chat.messages` on the way in.
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for role, content in turns:
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        else:
            # Guessing would put one speaker's words in the other's mouth,
            # which is worse than refusing a row that should not exist.
            raise ValueError(f"Unknown role: {role}")
    return messages


def text_of(content) -> str:
    """One string out of whatever a model put in `content`.

    A reply can arrive as a plain string or as a list of content blocks. Storing
    the repr of a list is the sort of thing that only shows up on screen, so it
    is flattened at the boundary rather than anywhere later.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def reply(
    provider: str, api_key: str, model: str | None, turns: Sequence[tuple[str, str]]
) -> str:
    """The assistant's next turn, or ProviderError."""
    try:
        answer = chat_model(provider, api_key, model).invoke(to_messages(turns))
    except UnknownProvider:
        raise
    except Exception as error:  # every SDK's own failure type, flattened
        raise ProviderError(str(error)) from error

    text = text_of(answer.content).strip()
    if not text:
        # An empty assistant turn leaves a chat that reads as broken and a
        # transcript the summary would have to describe as nothing.
        raise ProviderError("The provider returned an empty reply.")
    return text
