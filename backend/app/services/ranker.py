"""
Does this word fit *here*? — a masked language model used as a judge.

The dictionary in `vocab.py` knows what a word's synonyms are but not which of
them belongs in the sentence in front of it, which is why "running through the
park" could be offered "escaping". A language model knows the opposite: it reads
the sentence and has no idea what a synonym is, which is why asking it directly
for replacements offers "small" for "big".

So neither generates here. The dictionary proposes and the model ranks:

    candidates ── WordNet ──▶  every synonym, right sense or wrong
                                        │
                                        ▼
    scores    ──  this file ──▶  how well each one reads in this sentence
                                        │
                                        ▼
    rungs                        the ones that fit, ordered by difficulty

Ranking rather than generating is also what lifts the vocabulary ceiling. A
masked slot emits exactly one token, and the model's ~30k-piece vocabulary has
no single token for "felicitous" — it is `fe ##lic ##ito ##us`, so no amount of
prompting makes a `[MASK]` produce it. Scoring a word you already hold has no
such limit: mask its pieces one at a time and read off how probable each was.
The words a generator structurally cannot say, a judge can happily score.
"""

import math
import os
from functools import lru_cache

from wordfreq import zipf_frequency

MODEL_NAME = os.getenv("MLM_MODEL", "distilbert-base-uncased")

# Candidates scoring this far below the original — in mean log-probability per
# token — are reading as wrong-sense rather than merely rarer. Rarity costs some
# probability all on its own, so the margin has to be loose enough not to punish
# a word simply for being unusual, which is the whole point of the ladder.
FIT_MARGIN = 4.5

# Ranking is only worth its latency when there is something to choose between.
MIN_CANDIDATES = 2


@lru_cache(maxsize=1)
def _model():
    """
    Tokenizer and model, loaded once per process on first use.

    Lazy on purpose: importing torch and materialising the weights costs seconds
    and hundreds of megabytes, and a deployment with ranking switched off should
    never pay for it.
    """
    import torch
    from transformers import AutoModelForMaskedLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForMaskedLM.from_pretrained(MODEL_NAME)
    model.eval()
    return torch, tokenizer, model


def _mean_log_prob(torch, tokenizer, model, sentence: str, start: int, end: int, candidate: str):
    """
    How well `candidate` reads in place of [start:end], per token.

    Pseudo-log-likelihood: put the candidate in, then hide one of its tokens at
    a time and ask the model how surprised it is to find it there. Averaging
    over the tokens rather than summing keeps a four-piece word comparable with
    a one-piece word — a sum would rank every long word last purely for being
    long, which is precisely the bias that made generation useless here.
    """
    filled = sentence[:start] + candidate + sentence[end:]
    encoded = tokenizer(filled, return_tensors="pt")
    ids = encoded["input_ids"][0]

    # Which tokens are the candidate's? Re-tokenise the prefix to find where it
    # begins; character offsets do not survive tokenisation.
    prefix = tokenizer(sentence[:start], add_special_tokens=False)["input_ids"]
    body = tokenizer(candidate, add_special_tokens=False)["input_ids"]
    first = 1 + len(prefix)  # 1 for [CLS]
    positions = range(first, first + len(body))
    if not body or first + len(body) > len(ids):
        return None

    # One masked copy per token of the candidate, scored in a single batch.
    batch = ids.repeat(len(body), 1)
    for row, position in enumerate(positions):
        batch[row][position] = tokenizer.mask_token_id

    with torch.no_grad():
        logits = model(input_ids=batch, attention_mask=torch.ones_like(batch)).logits

    total = 0.0
    for row, position in enumerate(positions):
        probabilities = torch.log_softmax(logits[row, position], dim=-1)
        total += float(probabilities[ids[position]])
    return total / len(body)


def score_in_context(
    sentence: str, start: int, end: int, candidates: list[str]
) -> dict[str, float] | None:
    """
    How well each candidate reads in place of [start:end].

    Returns None when there is nothing to judge or the model cannot be reached,
    so a caller can fall back to the dictionary alone rather than fail.
    """
    if len(candidates) < MIN_CANDIDATES or not sentence:
        return None

    try:
        torch, tokenizer, model = _model()
    except Exception:
        # A missing model is a degraded ladder, never a broken editor.
        return None

    scores: dict[str, float] = {}
    for candidate in candidates:
        score = _mean_log_prob(torch, tokenizer, model, sentence, start, end, candidate)
        if score is not None:
            scores[candidate] = score
    return scores or None


# Note on what this deliberately does *not* do: normalise by the candidate's own
# frequency. Subtracting the prior — pointwise mutual information, the textbook
# correction for "common words score well everywhere" — was tried and made
# things worse. It rewards rarity, and this ranker feeds a ladder that already
# climbs toward rarity, so the two compound: "running through the park" went
# straight back to offering "escaping" and "heading for the hills", the exact
# wrong-sense failure the ranking exists to remove. Raw fit is the better
# signal here precisely because the difficulty axis is applied separately,
# afterwards, by `_difficulty`.


def rank_senses(
    sentence: str, start: int, end: int, senses: list[list[str]]
) -> list[int] | None:
    """
    Which sense the word is being used in, judged by how its synonyms read.

    Scoring the *sense* rather than each word separately is the point. A fluency
    score cannot tell a wrong sense from a right one on its own — "this is a bad
    problem" reads perfectly well, so filtering loose candidates by fluency lets
    "bad" through as a synonym for "big". But a sense is a group of words that
    mean the same thing, and the group that belongs here reads well *as a group*
    while the wrong one does not. Judging them together is what makes the
    evidence discriminating.

    `senses` is one list of candidate surface forms per sense, in WordNet's
    order. Returns their indices best-first, or None when the model cannot
    judge.

    An order rather than a winner, because senses are uneven: WordNet's first
    sense of "run" contains nothing but "run", so taking only the best sense
    would often leave a ladder of one. The caller walks this order and stops
    once it has enough rungs, which prefers the right sense without letting a
    thin one empty the ladder.
    """
    flat = [word for sense in senses for word in sense]
    scores = score_in_context(sentence, start, end, list(dict.fromkeys(flat)))
    if not scores:
        return None

    rated: list[tuple[float, int]] = []
    for index, sense in enumerate(senses):
        marks = [scores[word] for word in sense if word in scores]
        if not marks:
            continue
        # The mean over the sense, not its best member: one lucky word should
        # not carry a sense that otherwise reads badly here.
        rated.append((sum(marks) / len(marks), index))

    rated.sort(reverse=True)
    return [index for _, index in rated] or None


def is_available() -> bool:
    """Whether ranking can run at all — used to decide, not to fail."""
    try:
        _model()
        return True
    except Exception:
        return False
