"""
Tests for vocabulary analysis (app/api/analyze.py).

Which words count as "difficult" is a judgement call that will move as the
scoring is tuned, so these assert on properties — ordering, capping, exclusion
— rather than on exact word lists, the same way test_vocab.py does.

The analytics page joins every note in the database into one request body, so
the cap is not a nicety: without it the response grows with the corpus.
"""

from wordfreq import zipf_frequency

from app.services import analysis as analysis_service
from app.services.analysis import difficulty

PLAIN = "The dog sat on the mat and looked at the door."
HARD = "The perspicacious archivist enumerated every recondite marginalium."


def analyse(client, content: str, title: str = "Note"):
    response = client.post(
        "/api/analyze/vocabulary", json={"title": title, "content": content}
    )
    assert response.status_code == 200
    return response.json()["vocabulary_analysis"]


class TestShape:
    def test_returns_definitions_and_a_count(self, client):
        analysis = analyse(client, HARD)

        assert set(analysis) >= {"definitions", "total_difficult_words"}
        assert analysis["total_difficult_words"] == len(analysis["definitions"])

    def test_definitions_are_keyed_by_word(self, client):
        analysis = analyse(client, HARD)

        assert all(isinstance(word, str) and word for word in analysis["definitions"])

    def test_plain_prose_yields_few_or_no_difficult_words(self, client):
        plain = analyse(client, PLAIN)
        hard = analyse(client, HARD)

        assert plain["total_difficult_words"] < hard["total_difficult_words"]

    def test_empty_content_is_not_an_error(self, client):
        analysis = analyse(client, "")

        assert analysis["definitions"] == {}
        assert analysis["total_difficult_words"] == 0


class TestOrdering:
    def test_hardest_words_come_first(self, client):
        analysis = analyse(client, "The archivist was perspicacious and recondite.")

        words = list(analysis["definitions"])
        frequencies = [zipf_frequency(word, "en") for word in words]
        assert frequencies == sorted(frequencies)

    def test_the_cap_keeps_the_hardest_not_the_plainest(self, client, monkeypatch):
        # The direction of the sort is only observable once the cap bites, and
        # getting it backwards would silently return the easiest words — which
        # still passes every other test here.
        monkeypatch.setattr(analysis_service, "MAX_WORDS", 1)
        analysis = analyse(client, "The archivist was perspicacious.")

        assert list(analysis["definitions"]) == ["perspicacious"]


class TestCapping:
    def test_the_word_count_is_capped(self, client):
        # Far more distinct rare words than the cap allows.
        corpus = " ".join(
            [HARD] * 40 + ["obfuscate", "peregrinate", "lugubrious", "sagacity"] * 40
        )
        analysis = analyse(client, corpus)

        assert analysis["total_difficult_words"] <= analysis_service.MAX_WORDS

    def test_a_word_is_reported_once_however_often_it_appears(self, client):
        analysis = analyse(client, "recondite recondite recondite")

        assert list(analysis["definitions"]).count("recondite") <= 1


class TestKnownWords:
    def test_known_words_are_left_out(self, client):
        before = analyse(client, HARD)
        assert before["total_difficult_words"] > 0

        first = next(iter(before["definitions"]))
        client.post("/api/words/known", json={"words": [first]})

        after = analyse(client, HARD)
        assert first not in after["definitions"]
        assert after["total_difficult_words"] == before["total_difficult_words"] - 1


class TestDifficulty:
    """
    The sort key itself, rather than its effect through the endpoint.

    It is the one thing this module borrows from elsewhere, and the borrowing
    is about to change: the ladder that used to own `difficulty` is going, so
    these pin the behaviour across the move rather than describing anything
    new. Ascending, plainest first.
    """

    def test_frequency_decides(self):
        assert difficulty("dog") < difficulty("recondite")

    def test_a_phrase_scores_by_its_rarest_word(self):
        # Not by the phrase as a whole: multiplying the parts' probabilities
        # would make every phrase look vanishingly rare.
        assert difficulty("give up") < difficulty("relinquish")

    def test_a_phrase_loses_a_tie_to_a_single_word(self):
        rarest, phrase, _, _ = difficulty("give up")

        assert phrase == 0
        assert difficulty("relinquish")[1] == 1

    def test_syllables_break_a_tie_before_length_does(self):
        _, _, syllables, length = difficulty("archivist")

        assert syllables == 3
        assert length == len("archivist")
