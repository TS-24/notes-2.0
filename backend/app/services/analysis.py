"""
Which words in a note are worth learning?

The word ladder in `vocab.py` answers "what could this word be instead"; this
answers the prior question of which words are worth asking that about at all.
Both lean on the same signal — how often a word is actually used — so the
difficulty ordering is imported rather than re-derived.

Difficulty is a threshold on frequency, not a model. A word is hard because
readers rarely meet it, and `wordfreq` measures exactly that. Anything more
elaborate would be guessing at a reader this app knows nothing about, which is
what the known-words list is for instead.
"""

import regex
from nltk.corpus import wordnet
from wordfreq import zipf_frequency

from .vocab import difficulty

# Zipf frequency at or below which a word counts as difficult.
#
# The Zipf scale is logarithmic: 7 is "the", 5 is "happy", 4 is "ancient",
# 3 is "brevity", 2 is "recondite". Three is the point where words stop being
# merely uncommon and start being ones a reader plausibly hasn't met — above
# it the list fills with ordinary vocabulary and the feature reads as noise.
MAX_ZIPF = 3.0

# The shortest word worth offering. Below this the candidates are abbreviations
# and fragments that are rare only because they are not really words.
MIN_LENGTH = 4

# How many words one analysis may return.
#
# Not a nicety: analytics.tsx joins the content of *every* note into a single
# request, so without a cap the response — and the word cloud rendered from it
# — grows without bound as the user writes more.
MAX_WORDS = 50

_TOKEN = regex.compile(r"[\p{L}'’-]+")


def _definition(word: str) -> str | None:
    """WordNet's first gloss for a word, or None if it has none.

    `morphy` first so that "enumerated" finds the entry filed under
    "enumerate". A word with no synset at all is almost always a proper noun, a
    typo, or a fragment — not vocabulary — so the caller drops it rather than
    showing a word with nothing to say about it.
    """
    synsets = wordnet.synsets(word)
    if not synsets:
        lemma = wordnet.morphy(word)
        synsets = wordnet.synsets(lemma) if lemma else []
    return synsets[0].definition() if synsets else None


def difficult_words(content: str, known: set[str] = frozenset()) -> dict[str, str]:
    """
    The difficult words in `content`, hardest first, with their definitions.

    Case is folded for comparison but the lower-cased form is what comes back:
    the caller shows these as vocabulary rather than as quotations, so
    "Recondite" at the start of a sentence and "recondite" inside one are the
    same word to learn, not two.
    """
    seen: dict[str, float] = {}
    for match in _TOKEN.finditer(content):
        word = match.group().lower().strip("'’-")
        if len(word) < MIN_LENGTH or word in seen or word in known:
            continue
        frequency = zipf_frequency(word, "en")
        # Zero means wordfreq has never seen it, which is a typo far more often
        # than it is a rare word worth teaching.
        if frequency <= 0 or frequency > MAX_ZIPF:
            continue
        seen[word] = frequency

    # Hardest first, which is the reverse of the ladder's ordering — it climbs
    # from plain to rare, and this is a list of what to learn. The direction
    # matters because of the cap below: truncating a plainest-first list would
    # throw away exactly the words worth showing.
    definitions: dict[str, str] = {}
    for word in sorted(seen, key=difficulty, reverse=True):
        gloss = _definition(word)
        if gloss is None:
            continue
        definitions[word] = gloss
        if len(definitions) == MAX_WORDS:
            break
    return definitions
