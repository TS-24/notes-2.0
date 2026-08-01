"""
The word ladder — the vocabulary behind the roller's chevrons.

WordNet supplies synonyms but has no notion of formality, so on its own it
cannot answer "give me a harder word for this". Word frequency supplies the
missing axis: rare words read as formal, technical, and difficult; common words
read as casual and plain. A ladder is therefore a word's synonyms ordered by how
common they are, with the word itself standing on its own rung — climbing up
steps toward the rarer end, climbing down toward the plainer one.

    use (5.81)  ·  leverage (3.88)  ·  utilise (2.96)
    ←  plainer                          rarer  →

Everything here is pure — no database, no request. That is what makes the
scoring testable, which matters because the scoring is the part that will need
tuning against real prose.
"""

from dataclasses import dataclass

import pyphen
from lemminflect import getAllInflections, getInflection
from nltk.corpus import wordnet
from wordfreq import zipf_frequency

# How far the ladder may reach in each direction. A cap keeps one absurd rarity
# from sitting at the top of every climb, and keeps the payload small enough to
# send in one request — which is the point of sending a ladder at all rather
# than answering one step at a time.
RUNGS_EACH_WAY = 3

# How many WordNet senses to draw rungs from. WordNet orders a word's synsets
# most-used first, and the tail is where the wrong-sense synonyms live: at three
# senses "big" starts offering "bad", and the whole list gives "gravid" and
# "cock-a-hoop". Two is the point where the rungs stay on-sense without the
# ladder collapsing to nothing. A short ladder is a small disappointment; a
# wrong-sense synonym is a visible bug, so err toward short.
SENSES = 2

# WordNet's part-of-speech codes, mapped to the universal tags lemminflect
# wants. Adjective satellites ("s") inflect the same way as adjectives.
_POS_TO_UPOS = {"n": "NOUN", "v": "VERB", "a": "ADJ", "s": "ADJ", "r": "ADV"}

_HYPHENATOR = pyphen.Pyphen(lang="en_US")


@dataclass(frozen=True)
class Ladder:
    """A word's rungs, ordered plainest first."""

    word: str
    """What the caller asked about, untouched."""
    lemma: str
    """Its dictionary form — what WordNet is actually indexed by."""
    pos: str
    """The WordNet part of speech the rungs were drawn from."""
    origin_index: int
    """Where `word` itself stands. Up is `+1`, down is `-1`."""
    rungs: list[str]


def _syllables(word: str) -> int:
    return len(_HYPHENATOR.positions(word)) + 1


def _difficulty(word: str) -> tuple[float, int, int]:
    """
    Sort key, ascending — plainest first.

    Frequency does the real work. Syllable count and length only break ties
    between words used about equally often, where the longer, knottier one is
    the one that reads as harder.
    """
    return (-zipf_frequency(word, "en"), _syllables(word), len(word))


def _resolve(surface: str, pos: str | None) -> tuple[str, str] | None:
    """
    The dictionary form of `surface`, and the part of speech to read it as.

    A word can be several parts of speech at once — "running" is both a noun and
    a verb — and drawing rungs from more than one would mean offering a noun as
    the replacement for a verb. So commit to a single one: the sense with the
    most synsets, a decent proxy for the reading a writer most likely meant.
    """
    candidates = [pos] if pos else list(_POS_TO_UPOS)
    best: tuple[str, str, int] | None = None
    for part in candidates:
        if part not in _POS_TO_UPOS:
            continue
        lemma = wordnet.morphy(surface.lower(), part)
        if not lemma:
            continue
        senses = len(wordnet.synsets(lemma, pos=part))
        if senses and (best is None or senses > best[2]):
            best = (lemma, part, senses)
    return (best[0], best[1]) if best else None


def _inflection_of(surface: str, lemma: str, upos: str) -> str | None:
    """
    The tag describing how `surface` was inflected off `lemma` — `VBG` for
    "running", `NNS` for "houses". `None` when the word is already its own
    dictionary form and there is nothing to restore.
    """
    if surface.lower() == lemma.lower():
        return None
    for tag, forms in getAllInflections(lemma, upos=upos).items():
        if surface.lower() in {form.lower() for form in forms}:
            return tag
    return None


def _wear_the_original_form(candidate: str, tag: str | None, surface: str) -> str:
    """
    Dress a replacement to match the word it is standing in for.

    WordNet is a dictionary, so its lemmas come back uninflected. Without this,
    rolling "running" would offer "sprint" and drop it straight into the
    sentence. Irregular words lemminflect cannot inflect keep the dictionary
    form rather than having one invented for them.
    """
    word = candidate
    if tag:
        forms = getInflection(candidate, tag, inflect_oov=True)
        if forms:
            word = forms[0]
    if surface.isupper() and len(surface) > 1:
        return word.upper()
    if surface[:1].isupper():
        return word[:1].upper() + word[1:]
    return word


def word_ladder(word: str, pos: str | None = None) -> Ladder:
    """
    Build the ladder for `word`, plainest rung first.

    Falls back to a single rung — the word standing alone — whenever there is
    nothing to offer: an unknown word, a closed-class word like "the", or a word
    whose only synonyms are multi-word phrases.
    """
    surface = word.strip()
    if not surface:
        return Ladder(word=word, lemma=word, pos="", origin_index=0, rungs=[word])

    resolved = _resolve(surface, pos)
    if resolved is None:
        return Ladder(
            word=surface, lemma=surface, pos=pos or "", origin_index=0, rungs=[surface]
        )
    lemma, wn_pos = resolved

    candidates = {lemma}
    for synset in wordnet.synsets(lemma, pos=wn_pos)[:SENSES]:
        for name in synset.lemma_names():
            # WordNet joins multi-word lemmas with an underscore ("give_up").
            # They cannot be swapped into the span of a single word.
            if "_" in name:
                continue
            # Zero means the word appears nowhere in the frequency corpus at
            # all — WordNet debris that would otherwise sort straight to the top
            # as the "hardest" rung. Note this is the only frequency filter
            # worth having: a *floor* cannot separate archaic from merely rare
            # ("shew" scores 2.46, above both "obfuscate" at 2.28 and
            # "felicitous" at 1.86), so it would cut good rungs and keep junk.
            if zipf_frequency(name, "en") == 0:
                continue
            candidates.add(name.lower())

    ordered = sorted(candidates, key=_difficulty)
    origin = ordered.index(lemma)
    start = max(0, origin - RUNGS_EACH_WAY)
    ordered = ordered[start : origin + RUNGS_EACH_WAY + 1]
    origin -= start

    tag = _inflection_of(surface, lemma, _POS_TO_UPOS[wn_pos])
    rungs: list[str] = []
    origin_index = 0
    for index, candidate in enumerate(ordered):
        # The original keeps the exact form the caller sent, so climbing back
        # down to it is a true round trip rather than a near miss.
        if index == origin:
            origin_index = len(rungs)
            rungs.append(surface)
            continue
        rung = _wear_the_original_form(candidate, tag, surface)
        if rung not in rungs and rung.lower() != surface.lower():
            rungs.append(rung)

    return Ladder(
        word=surface,
        lemma=lemma,
        pos=wn_pos,
        origin_index=origin_index,
        rungs=rungs,
    )
