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
import regex
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

# The longest phrase worth testing at the caret. WordNet's multi-word lemmas are
# almost all two or three tokens ("give up", "a great deal"), and every extra
# token multiplies the windows to test for a vanishing return.
MAX_PHRASE_TOKENS = 4

_TOKEN = regex.compile(r"[\p{L}\p{N}'’-]+")

# Articles are not looked up — nobody wants synonyms for "an" — but they have to
# travel inside the replaced span, because the choice between them depends on
# the word that follows. Replace "an example" with "model" alone and the
# sentence reads "an model".
ARTICLES = {"a", "an"}

# A vowel *letter* is only a proxy for a vowel *sound*, and the exceptions are
# common enough to be worth naming: "an hour", but "a university".
_SOUNDS_VOWEL = {
    "hour", "hourly", "honest", "honestly", "honesty", "honour", "honor",
    "honourable", "honorable", "heir", "heiress", "heirloom",
}
_SOUNDS_CONSONANT = {
    "european", "eulogy", "euphemism", "once", "one", "ubiquitous", "unicorn",
    "uniform", "union", "unique", "unit", "united", "unity", "universal",
    "universe", "university", "usage", "use", "used", "useful", "user", "usual",
    "utility",
}


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


def _difficulty(unit: str) -> tuple[float, int, int, int]:
    """
    Sort key, ascending — plainest first.

    Frequency does the real work. Syllable count and length only break ties
    between units used about equally often, where the longer, knottier one is
    the one that reads as harder.

    A phrase is scored by its *rarest* word rather than by the phrase as a
    whole. Scoring the whole thing would multiply the parts' probabilities and
    make every phrase look vanishingly rare — which is backwards, since English
    phrases the plain way round: "give up" is the casual form and "relinquish"
    the formal one. The rarest-word rule gets that right, and the phrase flag
    settles ties in the same direction.
    """
    words = unit.replace("_", " ").split()
    rarest = min(zipf_frequency(word, "en") for word in words) if words else 0.0
    return (-rarest, 0 if len(words) > 1 else 1, _syllables(unit), len(unit))


def _resolve(surface: str, pos: str | None) -> tuple[str, str] | None:
    """
    The dictionary form of `surface`, and the part of speech to read it as.

    A word can be several parts of speech at once — "running" is both a noun and
    a verb — and drawing rungs from more than one would mean offering a noun as
    the replacement for a verb. So commit to a single one: the sense with the
    most synsets, a decent proxy for the reading a writer most likely meant.
    """
    # A phrase is stored under a single underscored key, and the caller may hand
    # us an inflected one ("gave up"), so lemmatise before looking it up —
    # otherwise the inflected form finds nothing and the phrase silently loses
    # its ladder.
    if " " in surface:
        key = _phrase_key(surface.split())
        if key is None:
            return None
        return key, wordnet.synsets(key)[0].pos()

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
    # Only the head of a phrase carries inflection ("gave up", not "gave upped"),
    # so compare heads.
    surface_head = surface.replace("_", " ").split()[0].lower()
    lemma_head = lemma.replace("_", " ").split()[0].lower()
    if surface_head == lemma_head:
        return None
    for tag, forms in getAllInflections(lemma_head, upos=upos).items():
        if surface_head in {form.lower() for form in forms}:
            return tag
    return None


def _wear_the_original_form(
    candidate: str, tag: str | None, surface: str, wn_pos: str = "v"
) -> str:
    """
    Dress a replacement to match the word it is standing in for.

    WordNet is a dictionary, so its lemmas come back uninflected. Without this,
    rolling "running" would offer "sprint" and drop it straight into the
    sentence. Irregular words lemminflect cannot inflect keep the dictionary
    form rather than having one invented for them.
    """
    word = candidate.replace("_", " ")
    if tag:
        # Which token carries the inflection depends on what kind of phrase it
        # is. A verb phrase inflects at the head — "gave up", never "gave
        # upped". A noun compound inflects at the tail — "business firms", never
        # "businesses firm".
        parts = word.split()
        at = len(parts) - 1 if wn_pos == "n" else 0
        forms = getInflection(parts[at], tag, inflect_oov=True)
        if forms:
            parts[at] = forms[0]
            word = " ".join(parts)
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
        related = [synset]
        # Adjectives are the thinnest part of WordNet's synonymy: "big" and
        # "large" are the whole of big's synset, and "fast" has no synonym at
        # all. The richness lives one hop away, in the satellite cluster around
        # the head adjective — following it takes big from 2 candidates to 88
        # and fast from 1 to 28, and the words it reaches ("arduous",
        # "alacritous", "Brobdingnagian") are exactly the rare end that "up"
        # climbs toward.
        if wn_pos in {"a", "s"}:
            related += synset.similar_tos()
        for near in related:
            for name in near.lemma_names():
                # Multi-word lemmas are idiomatic and useful for nouns and verbs
                # ("give up", "a great deal") but not for modifiers, where the
                # satellite clusters hold constructions like "too_large" that
                # read as broken English once dropped into a sentence.
                if "_" in name and wn_pos not in {"n", "v"}:
                    continue
                # Zero means the word appears nowhere in the frequency corpus at
                # all — WordNet debris that would otherwise sort straight to the
                # top as the "hardest" rung. Note this is the only frequency
                # filter worth having: a *floor* cannot separate archaic from
                # merely rare ("shew" scores 2.46, above both "obfuscate" at
                # 2.28 and "felicitous" at 1.86), so it would cut good rungs and
                # keep junk.
                if zipf_frequency(name.replace("_", " "), "en") == 0:
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
        rung = _wear_the_original_form(candidate, tag, surface, wn_pos)
        if rung not in rungs and rung.lower() != surface.lower():
            rungs.append(rung)

    return Ladder(
        word=surface,
        lemma=lemma,
        pos=wn_pos,
        origin_index=origin_index,
        rungs=rungs,
    )


# --------------------------------------------------------------------------
# Units: what the caret is actually standing in
#
# A word on its own is the wrong unit surprisingly often. "give up" means
# something its two words do not, and it has a ladder — forfeit, waive, forgo —
# that neither "give" nor "up" can reach. An article is the opposite case: "an"
# has no ladder of its own, but it has to travel with the word it attaches to,
# because whether it reads "a" or "an" depends on what replaces that word.
#
# So the caret resolves to a *unit*: the longest phrase WordNet knows, else the
# single word, with any article in front folded in.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Unit:
    """What the caret is standing in, and what should be replaced."""

    start: int
    """Where the replaced span begins — before the article, when there is one."""
    end: int
    text: str
    """Exactly the text in that span, article included."""
    lookup: str
    """The WordNet key: lemmatised, underscored, no article."""
    article: str
    """The article being carried, or empty."""


def indefinite_article(following: str) -> str:
    """"a" or "an", by the sound the next word starts with."""
    head = following.replace("_", " ").split()
    if not head:
        return "a"
    first = head[0].lower().strip("'’-")
    if first in _SOUNDS_VOWEL:
        return "an"
    if first in _SOUNDS_CONSONANT:
        return "a"
    return "an" if first[:1] in "aeiou" else "a"


def _phrase_key(tokens: list[str]) -> str | None:
    """
    The WordNet key for these tokens, if it knows them as a phrase.

    Tries the phrase as written first, then lemmatised — "gave up" has to find
    "give_up", and "neural networks" has to find "neural_network". Only the head
    of a verb phrase and the tail of a noun phrase ever inflect, so those are the
    only two positions worth lemmatising.
    """
    words = [token.lower() for token in tokens]
    attempts = ["_".join(words)]

    head = wordnet.morphy(words[0], "v")
    if head and head != words[0]:
        attempts.append("_".join([head, *words[1:]]))

    tail = wordnet.morphy(words[-1], "n")
    if tail and tail != words[-1]:
        attempts.append("_".join([*words[:-1], tail]))

    for key in attempts:
        if wordnet.synsets(key):
            return key
    return None


def unit_at(sentence: str, caret: int) -> Unit | None:
    """
    The unit the caret is standing in, or None when it is not in a word.

    Longest match wins: a caret inside "up" in "give up" resolves to the phrase,
    not to the preposition, because the phrase is the thing with a ladder.
    """
    tokens = [(match.start(), match.end(), match.group()) for match in _TOKEN.finditer(sentence)]
    here = next(
        (i for i, (start, end, _) in enumerate(tokens) if start <= caret <= end), None
    )
    if here is None:
        return None

    start, end, text = tokens[here]
    lookup = text.lower()

    # Longest window first, so "a great deal" beats "great deal" beats "deal".
    found = False
    for size in range(min(MAX_PHRASE_TOKENS, len(tokens)), 1, -1):
        if found:
            break
        first = max(0, here - size + 1)
        for begin in range(first, here + 1):
            window = tokens[begin : begin + size]
            if len(window) < size or here >= begin + size:
                continue
            key = _phrase_key([token for _, _, token in window])
            if key:
                start, end = window[0][0], window[-1][1]
                text, lookup, found = sentence[start:end], key, True
                break

    # An article in front joins the unit — it is not looked up, but it is
    # replaced, so that "an example" can become "a model".
    article = ""
    before = here - (len(text.split()) - 1) - 1
    if 0 <= before < len(tokens) and tokens[before][2].lower() in ARTICLES:
        article = tokens[before][2]
        start = tokens[before][0]
        text = sentence[start:end]

    return Unit(start=start, end=end, text=text, lookup=lookup, article=article)


def unit_ladder(sentence: str, caret: int) -> tuple[Unit, Ladder] | None:
    """
    The ladder for whatever the caret is standing in.

    This is the entry point the API uses. `Ladder.rungs` are ready to drop
    straight into `Unit.start:end` — article included and agreeing, phrase
    inflected to match what was there.
    """
    unit = unit_at(sentence, caret)
    if unit is None:
        return None

    # Built from what is actually written, not from the dictionary key: the key
    # is lemmatised, and handing that over would lose the tense — "gave up"
    # would come back with "give up" on its own rung and break the round trip.
    surface = unit.text[len(unit.article) :].strip()
    ladder = word_ladder(surface)

    if not unit.article:
        # The rungs still have to carry the original's exact surface form on its
        # own rung, which `word_ladder` guarantees.
        return unit, ladder

    rungs = [f"{_match_article_case(unit.article, indefinite_article(rung))} {rung}" for rung in ladder.rungs]
    return unit, Ladder(
        word=unit.text,
        lemma=ladder.lemma,
        pos=ladder.pos,
        origin_index=ladder.origin_index,
        rungs=rungs,
    )


def _match_article_case(original: str, article: str) -> str:
    """Keep a capitalised "An" capitalised when it becomes "A"."""
    return article.capitalize() if original[:1].isupper() else article
