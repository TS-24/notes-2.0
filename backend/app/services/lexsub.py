"""
The contextual engine — lexical substitution with a masked language model.

Where `vocab.py` asks a dictionary "what are this word's synonyms?", this asks a
language model "what else could stand in this exact slot?". The word is blanked
out of its own sentence and the model proposes fillers:

    "I worked on a ML [MASK] for risk evaluation."
                       ↑ the model sees the whole sentence, so "model" here is
                         a thing you build, not someone on a runway

That is the whole point of it. WordNet cannot tell those apart, because it never
sees the sentence — it only ever receives the bare word.

Three things about this approach are worth knowing before reading the code,
because they shape every filter below:

1. **Fill-mask proposes words that FIT, not words that MEAN THE SAME.** "The
   results were good" takes "bad" perfectly well. There is no synonymy
   guarantee anywhere in this file; ranking cannot add one.

2. **One mask emits one token.** Anything outside the model's ~30k wordpiece
   vocabulary comes back in fragments and has to be dropped — and the words that
   split are disproportionately the rare ones ("felicitous", "obfuscate",
   "magnanimous" all split; "use", "help", "big" do not). The filter is
   therefore biased against exactly the end of the ladder that "up" climbs
   toward.

3. **The answer depends on the whole sentence**, so unlike a WordNet ladder it
   cannot be cached under the word alone.

None of these are bugs to be fixed later; they are properties of the method.
"""

import os
import re
from dataclasses import dataclass
from functools import lru_cache

from wordfreq import zipf_frequency

from .vocab import RUNGS_EACH_WAY, Ladder, difficulty

MODEL_NAME = os.getenv("MLM_MODEL", "distilbert-base-uncased")

# How many predictions to pull before filtering. Most are discarded — wordpiece
# fragments, punctuation, the original word, casing duplicates — so this has to
# be generous to leave a ladder behind.
TOP_K = 120

# A candidate has to look like a word: letters, optionally hyphenated. This also
# throws out the subword continuations ("##ing"), which are the single largest
# category of junk coming back.
WORD_LIKE = re.compile(r"^[a-z][a-z\-']*$")


@dataclass(frozen=True)
class Prediction:
    word: str
    score: float


@lru_cache(maxsize=1)
def _pipeline():
    """
    The model, loaded once per process on first use.

    Deliberately lazy: importing torch and materialising the weights takes a
    few seconds and a few hundred megabytes, and the WordNet engine should not
    pay for it when the contextual one is switched off.
    """
    from transformers import pipeline

    return pipeline("fill-mask", model=MODEL_NAME, top_k=TOP_K)


def _predict(sentence: str, start: int, end: int) -> list[Prediction]:
    """Blank out [start:end] and ask the model what belongs there."""
    fill = _pipeline()
    masked = sentence[:start] + fill.tokenizer.mask_token + sentence[end:]
    out: list[Prediction] = []
    for item in fill(masked):
        token = item["token_str"].strip().lower()
        if not WORD_LIKE.match(token):
            continue
        out.append(Prediction(word=token, score=float(item["score"])))
    return out


def word_ladder_in_context(
    word: str, sentence: str, start: int, end: int, floor: float = 0.0
) -> Ladder:
    """
    Build a ladder for the word at [start:end] of `sentence`.

    Same shape as `vocab.word_ladder` — rungs ordered plainest first, with the
    original standing on its own rung — so the two engines are interchangeable
    from the caller's point of view and can be compared directly.

    `floor` drops predictions the model is not confident about. Raising it trades
    ladder length for relevance, and is the main dial worth turning here.
    """
    surface = word.strip()
    alone = Ladder(word=surface, lemma=surface, pos="", origin_index=0, rungs=[surface])
    if not surface or not sentence:
        return alone

    # The model needs the sentence with a hole in it; if the offsets do not
    # actually point at the word, we would be masking the wrong thing.
    if sentence[start:end].strip().lower() != surface.lower():
        return alone

    candidates = {}
    for prediction in _predict(sentence, start, end):
        if prediction.score < floor:
            continue
        if prediction.word == surface.lower():
            continue
        # No usage signal — same filter the WordNet engine applies, and for the
        # same reason: these would sort straight to the "hardest" end.
        if zipf_frequency(prediction.word, "en") == 0:
            continue
        candidates[prediction.word] = prediction.score

    if not candidates:
        return alone

    ordered = sorted({*candidates, surface.lower()}, key=difficulty)
    origin = ordered.index(surface.lower())
    lo = max(0, origin - RUNGS_EACH_WAY)
    ordered = ordered[lo : origin + RUNGS_EACH_WAY + 1]
    origin -= lo

    rungs: list[str] = []
    origin_index = 0
    for index, candidate in enumerate(ordered):
        if index == origin:
            origin_index = len(rungs)
            rungs.append(surface)
            continue
        rungs.append(_match_case(surface, candidate))

    return Ladder(
        word=surface,
        lemma=surface,
        # No part of speech: the model never resolves one. The field stays for
        # shape compatibility with the WordNet engine.
        pos="",
        origin_index=origin_index,
        rungs=rungs,
    )


def _match_case(surface: str, candidate: str) -> str:
    """
    The model is uncased, so everything comes back lowercase.

    Note there is no inflection step here, unlike the WordNet engine: the model
    predicts a form that already fits the slot, so "running" attracts "walking"
    rather than "walk". That is genuinely simpler — but it is a statistical
    habit, not a guarantee, and nothing downstream can check it.
    """
    if surface.isupper() and len(surface) > 1:
        return candidate.upper()
    if surface[:1].isupper():
        return candidate[:1].upper() + candidate[1:]
    return candidate
