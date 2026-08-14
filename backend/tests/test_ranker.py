"""
Tests for sense ranking (app/services/ranker.py).

The real model is never called here. What matters is not whether a hosted
embedding model has good taste — that is a judgement these tests cannot make —
but that the module returns an order when it can and None when it cannot.
The None path is load-bearing: it is what the app does offline, and vocab.py
falls back to the dictionary's own ordering on it at all three call sites.
"""

import pytest

from app.services import ranker

SENTENCE = "I had to run to the shop."
START, END = 11, 14  # "run"
SENSES = [["run", "jog"], ["operate", "manage"]]


@pytest.fixture(autouse=True)
def _ranking_on(monkeypatch):
    """A clean client, and credentials present.

    A token is what "ranking is on" now means — without one the module
    short-circuits before reaching a model at all, which is its own test below
    rather than the background for every other one.
    """
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    ranker._client.cache_clear()
    yield
    # Guarded: teardown runs before monkeypatch puts the real _client back, so
    # by now it is usually a stub with no cache to clear.
    clear = getattr(ranker._client, "cache_clear", None)
    if clear is not None:
        clear()


def fake_embeddings(monkeypatch, vectors):
    """Answer feature_extraction with `vectors`, in call order."""
    def _embed(sentences):
        return vectors
    monkeypatch.setattr(ranker, "_client", lambda: type("C", (), {"feature_extraction": staticmethod(_embed)})())


class TestOrdering:
    def test_the_closer_sense_comes_first(self, monkeypatch):
        # Original, then run/jog (near it), then operate/manage (far from it).
        fake_embeddings(monkeypatch, [
            [1.0, 0.0],
            [0.99, 0.14], [0.98, 0.20],
            [0.0, 1.0], [0.10, 0.99],
        ])

        assert ranker.rank_senses(SENTENCE, START, END, SENSES) == [0, 1]

    def test_the_order_flips_with_the_evidence(self, monkeypatch):
        fake_embeddings(monkeypatch, [
            [1.0, 0.0],
            [0.0, 1.0], [0.10, 0.99],
            [0.99, 0.14], [0.98, 0.20],
        ])

        assert ranker.rank_senses(SENTENCE, START, END, SENSES) == [1, 0]

    def test_every_sense_is_accounted_for(self, monkeypatch):
        fake_embeddings(monkeypatch, [
            [1.0, 0.0],
            [0.9, 0.1], [0.8, 0.2],
            [0.7, 0.3], [0.6, 0.4],
        ])

        order = ranker.rank_senses(SENTENCE, START, END, SENSES)
        assert sorted(order) == list(range(len(SENSES)))

    def test_a_sense_is_judged_as_a_group_not_by_its_best_word(self, monkeypatch):
        # Sense 0 has one excellent word and one terrible one; sense 1 is
        # consistently good. The mean should prefer sense 1.
        fake_embeddings(monkeypatch, [
            [1.0, 0.0],
            [1.0, 0.0], [0.0, 1.0],
            [0.9, 0.1], [0.9, 0.1],
        ])

        assert ranker.rank_senses(SENTENCE, START, END, SENSES) == [1, 0]


class TestDegradation:
    """Every one of these must return None rather than raise.

    vocab.py treats None as "rank nothing, use the dictionary order". A raise
    here would take the word roller down instead of quietly flattening it.
    """

    def test_a_network_failure_returns_none(self, monkeypatch):
        def _raise(sentences):
            raise ConnectionError("no route to host")
        monkeypatch.setattr(ranker, "_client", lambda: type("C", (), {"feature_extraction": staticmethod(_raise)})())

        assert ranker.rank_senses(SENTENCE, START, END, SENSES) is None

    def test_a_missing_token_returns_none_without_calling_out(self, monkeypatch):
        # Not just None — None *cheaply*. A hosted ranker that is simply absent
        # must not cost a timeout on every uncached lookup to establish that,
        # which is what the env-only `enabled()` check exists to prevent.
        monkeypatch.delenv("HF_TOKEN", raising=False)

        def _fail(sentences):
            raise AssertionError("should not have been called without a token")
        monkeypatch.setattr(ranker, "_client", lambda: type("C", (), {"feature_extraction": staticmethod(_fail)})())

        assert ranker.rank_senses(SENTENCE, START, END, SENSES) is None

    def test_a_short_response_returns_none(self, monkeypatch):
        # Fewer vectors than sentences sent — a truncated or reshaped reply.
        fake_embeddings(monkeypatch, [[1.0, 0.0], [0.9, 0.1]])

        assert ranker.rank_senses(SENTENCE, START, END, SENSES) is None

    def test_a_malformed_response_returns_none(self, monkeypatch):
        fake_embeddings(monkeypatch, None)

        assert ranker.rank_senses(SENTENCE, START, END, SENSES) is None

    def test_too_few_candidates_never_calls_the_model(self, monkeypatch):
        def _fail(sentences):
            raise AssertionError("should not have been called")
        monkeypatch.setattr(ranker, "_client", lambda: type("C", (), {"feature_extraction": staticmethod(_fail)})())

        assert ranker.rank_senses(SENTENCE, START, END, [["run"]]) is None

    def test_an_empty_sentence_returns_none(self, monkeypatch):
        assert ranker.rank_senses("", 0, 0, SENSES) is None


class TestTokenVectors:
    def test_per_token_vectors_are_pooled(self, monkeypatch):
        # Some models return a vector per token instead of one per sentence.
        fake_embeddings(monkeypatch, [
            [[1.0, 0.0], [1.0, 0.0]],
            [[0.9, 0.1], [0.9, 0.1]], [[0.8, 0.2], [0.8, 0.2]],
            [[0.0, 1.0], [0.0, 1.0]], [[0.1, 0.9], [0.1, 0.9]],
        ])

        assert ranker.rank_senses(SENTENCE, START, END, SENSES) == [0, 1]


class TestAvailability:
    def test_no_token_means_unavailable(self, monkeypatch):
        monkeypatch.delenv("HF_TOKEN", raising=False)

        assert ranker.is_available() is False

    def test_a_working_model_means_available(self, monkeypatch):
        monkeypatch.setenv("HF_TOKEN", "hf_test")
        fake_embeddings(monkeypatch, [[1.0, 0.0]])

        assert ranker.is_available() is True
