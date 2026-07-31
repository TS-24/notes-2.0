"""
Tests for the word ladder (app/services/vocab.py).

The ladder is the one piece of this app with real logic behind it and no UI in
the way, and its output is a judgement call about English rather than a fact —
so it is worth pinning down the *properties* that must hold, and being explicit
about the ones that only hold for WordNet's better-covered words.

These deliberately assert on shape and ordering rather than on exact word lists.
The rungs will move as the scoring is tuned; the invariants should not.
"""

import pytest

from app.services import vocab
from app.services.vocab import word_ladder


def zipf(word: str) -> float:
    from wordfreq import zipf_frequency

    return zipf_frequency(word, "en")


class TestShape:
    def test_the_word_is_always_on_its_own_ladder(self):
        ladder = word_ladder("help")
        assert ladder.rungs[ladder.origin_index] == "help"

    def test_rungs_run_plainest_to_rarest(self):
        ladder = word_ladder("help")
        frequencies = [zipf(rung) for rung in ladder.rungs]
        assert frequencies == sorted(frequencies, reverse=True)

    def test_ladder_is_capped_in_both_directions(self):
        ladder = word_ladder("show")
        assert ladder.origin_index <= vocab.RUNGS_EACH_WAY
        assert len(ladder.rungs) - ladder.origin_index - 1 <= vocab.RUNGS_EACH_WAY

    def test_no_rung_repeats(self):
        ladder = word_ladder("show")
        assert len(ladder.rungs) == len(set(ladder.rungs))


class TestNothingToOffer:
    """A word with no synonyms is not an error — it stands on a ladder of one."""

    @pytest.mark.parametrize("word", ["asdfqwerzz", "the", ""])
    def test_falls_back_to_a_single_rung(self, word):
        ladder = word_ladder(word)
        assert ladder.rungs == [word]
        assert ladder.origin_index == 0


class TestDirection:
    def test_a_plain_word_can_only_climb(self):
        # "help" is about as common as its synonyms get, so there is nothing
        # plainer to offer and the whole ladder sits above it.
        assert word_ladder("help").origin_index == 0

    def test_a_hard_word_has_plainer_rungs_below_it(self):
        ladder = word_ladder("utilise")
        assert ladder.origin_index > 0
        assert zipf(ladder.rungs[0]) > zipf("utilise")

    def test_the_original_appears_exactly_once(self):
        # What makes a climb reversible: if the original occurred twice, walking
        # back down could land on the other copy and the rung count would drift.
        ladder = word_ladder("assist")
        assert ladder.rungs.count("assist") == 1


class TestWearsTheOriginalForm:
    """
    WordNet is a dictionary, so its lemmas come back uninflected. Dropping a
    bare lemma into a sentence is the most visible way this feature can break.
    """

    def test_present_participle_stays_a_present_participle(self):
        rungs = word_ladder("running").rungs
        assert all(rung.endswith("ing") for rung in rungs), rungs

    def test_plural_stays_plural(self):
        rungs = word_ladder("houses").rungs
        assert all(rung.endswith("s") for rung in rungs), rungs

    def test_past_tense_stays_past_tense(self):
        ladder = word_ladder("said")
        assert ladder.lemma == "say"
        assert len(ladder.rungs) > 1

    def test_the_original_keeps_its_exact_form(self):
        # Not merely "an inflection of the same lemma" — the same characters, so
        # that climbing back down is a true round trip.
        ladder = word_ladder("running")
        assert ladder.rungs[ladder.origin_index] == "running"


class TestCapitalisation:
    def test_a_capitalised_word_gets_capitalised_rungs(self):
        rungs = word_ladder("Help").rungs
        assert all(rung[0].isupper() for rung in rungs), rungs

    def test_shouting_stays_shouting(self):
        rungs = word_ladder("HELP").rungs
        assert all(rung.isupper() for rung in rungs), rungs


class TestUnusableCandidates:
    def test_multi_word_lemmas_are_dropped(self):
        # WordNet joins these with an underscore; they cannot be swapped into
        # the span of a single word.
        for word in ["give", "run", "put", "help", "show", "big"]:
            assert not any("_" in rung for rung in word_ladder(word).rungs)

    def test_words_with_no_usage_signal_are_dropped(self):
        for word in ["big", "show", "happy"]:
            assert all(zipf(rung) > 0 for rung in word_ladder(word).rungs)


class TestPartOfSpeech:
    def test_an_explicit_part_of_speech_is_honoured(self):
        assert word_ladder("use", "v").pos == "v"
        assert word_ladder("use", "n").pos == "n"

    def test_rungs_come_from_one_part_of_speech_only(self):
        # Mixing them would offer a noun as the replacement for a verb.
        ladder = word_ladder("use", "v")
        assert "role" not in ladder.rungs
