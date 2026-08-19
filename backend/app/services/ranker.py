"""
Does this word fit *here*? — sense selection by semantic similarity.

The dictionary in `vocab.py` knows what a word's synonyms are but not which of
them belongs in the sentence in front of it, which is why "running through the
park" could be offered "escaping". Something has to read the sentence and say
which reading is the live one.

So the dictionary still proposes and this file still only ranks:

    candidates ── WordNet ──▶  every synonym, right sense or wrong
                                        │
                                        ▼
    order     ──  this file ──▶  which senses belong in this sentence
                                        │
                                        ▼
    rungs                        the ones that fit, ordered by difficulty

What it ranks *with* is a hosted embedding model rather than a local masked
language model. The question asked is "if I swap this sense in, is it still the
same sentence?" — each sense is substituted into the sentence, both versions
are embedded, and the senses whose substitution drifts least from the original
come first. Scoring the sense as a group rather than word by word is the part
worth keeping from the previous design: a lone word cannot distinguish a wrong
sense that happens to read fluently, but a group of words that all mean the
same thing either belongs here or does not.

This is a weaker signal than judging grammatical fit directly, and it is meant
to be: the feature degrades to the dictionary's own ordering whenever the model
cannot be reached, and that fallback is the normal offline state rather than an
error path. Every failure here returns None.
"""

import math
import os
from functools import lru_cache

MODEL_NAME = os.getenv("HF_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Ranking is only worth its latency when there is something to choose between.
MIN_CANDIDATES = 2

# The word roller's animation is 460ms and it asks for a ladder mid-keystroke.
# A slow rank has to become a dictionary ladder rather than a stalled reel, so
# this is deliberately shorter than a request would normally be given.
TIMEOUT_SECONDS = 3.0


@lru_cache(maxsize=1)
def _client():
    """
    The inference client, built once per process.

    Lazy because a deployment with ranking switched off should never pay for
    the import, and because the token is read at first use rather than at
    import — the desktop build supplies it after the process is already up.
    """
    from huggingface_hub import InferenceClient

    return InferenceClient(model=MODEL_NAME, token=os.getenv("HF_TOKEN"), timeout=TIMEOUT_SECONDS)


def enabled() -> bool:
    """
    Whether ranking should be attempted at all — env only, no network.

    Separate from `is_available` on purpose. This is checked on the hot path,
    before a ladder is built, so it has to be free; `is_available` proves the
    model answers and costs a round trip.

    Without it a token-less install would attempt a call on every uncached
    lookup and wait out the timeout before falling back — and since a ranked
    ladder is cached per sentence rather than per word, those misses are the
    common case. The old local model was always there or always absent; a
    hosted one is absent in a way that costs seconds, so absence has to be
    settled before the request rather than by it.
    """
    return bool(os.getenv("HF_TOKEN"))


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _flatten(vector):
    """
    Reduce whatever the endpoint returned to one list of floats.

    Sentence-transformers models return a vector per sentence, but some return
    a vector per *token* instead, which arrives as a list of lists. Averaging
    over that gives the sentence vector, and is a no-op for models that already
    pooled.
    """
    values = list(vector)
    if values and isinstance(values[0], (list, tuple)):
        columns = list(zip(*values))
        return [sum(column) / len(column) for column in columns]
    return [float(value) for value in values]


def _embed(sentences: list[str]) -> list[list[float]] | None:
    try:
        raw = _client().feature_extraction(sentences)
    except Exception:
        # No token, no network, a cold model, a timeout — all the same answer.
        return None
    try:
        embedded = [_flatten(vector) for vector in raw]
    except TypeError:
        return None
    if len(embedded) != len(sentences) or not all(embedded):
        return None
    return embedded


def rank_senses(
    sentence: str, start: int, end: int, senses: list[list[str]]
) -> list[int] | None:
    """
    Which sense the word is being used in, judged by what its synonyms do to
    the sentence.

    `senses` is one list of candidate surface forms per sense, in WordNet's
    order. Returns their indices best-first, or None when nothing can be
    judged.

    An order rather than a winner, because senses are uneven: WordNet's first
    sense of "run" contains nothing but "run", so taking only the best sense
    would often leave a ladder of one. The caller walks this order and stops
    once it has enough rungs, which prefers the right sense without letting a
    thin one empty the ladder.
    """
    if not enabled() or not sentence or not senses:
        return None
    if sum(len(sense) for sense in senses) < MIN_CANDIDATES:
        return None

    # One substituted sentence per candidate, kept alongside the sense it came
    # from so the scores can be pooled per sense afterwards.
    variants: list[str] = []
    owners: list[int] = []
    for index, sense in enumerate(senses):
        for word in sense:
            variants.append(sentence[:start] + word + sentence[end:])
            owners.append(index)
    if not variants:
        return None

    embedded = _embed([sentence] + variants)
    if embedded is None:
        return None
    original, rest = embedded[0], embedded[1:]

    totals: dict[int, list[float]] = {}
    for owner, vector in zip(owners, rest):
        totals.setdefault(owner, []).append(_cosine(original, vector))

    # The mean over the sense, not its best member: one lucky word should not
    # carry a sense that otherwise reads badly here.
    rated = [(sum(marks) / len(marks), index) for index, marks in totals.items() if marks]
    if not rated:
        return None
    rated.sort(reverse=True)
    return [index for _, index in rated]


def is_available() -> bool:
    """Whether ranking can run at all — used to decide, not to fail."""
    if not enabled():
        return False
    return _embed(["a test sentence"]) is not None
