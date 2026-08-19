"""
Tests for marking words as known (app/api/known_words.py).

The endpoint is called fire-and-forget from the note grid: the card is removed
from the UI first and the request goes out afterwards, so the caller never sees
the response. That shapes what matters here — it has to be idempotent and it
must not raise on input the UI would happily send twice.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import KnownWord


def known_words(db: Session) -> list[str]:
    return list(db.scalars(select(KnownWord.word).order_by(KnownWord.word)))


class TestMarking:
    def test_a_word_is_recorded(self, client, db):
        response = client.post("/api/words/known", json={"words": ["felicitous"]})

        assert response.status_code == 204
        assert known_words(db) == ["felicitous"]

    def test_several_words_in_one_call(self, client, db):
        client.post("/api/words/known", json={"words": ["arduous", "brevity"]})

        assert known_words(db) == ["arduous", "brevity"]

    def test_marking_the_same_word_twice_is_a_no_op(self, client, db):
        client.post("/api/words/known", json={"words": ["arduous"]})
        second = client.post("/api/words/known", json={"words": ["arduous"]})

        # Not a 409: the grid removes the card optimistically and may resend on
        # a retry, and a conflict there would surface as a console error for
        # something the user already did successfully.
        assert second.status_code == 204
        assert known_words(db) == ["arduous"]

    def test_a_repeat_inside_one_call_is_also_fine(self, client, db):
        client.post("/api/words/known", json={"words": ["arduous", "arduous"]})

        assert known_words(db) == ["arduous"]

    def test_words_are_owned_by_the_current_user(self, client, db, user):
        client.post("/api/words/known", json={"words": ["arduous"]})

        entry = db.scalars(select(KnownWord)).one()
        assert entry.user_id == user.id

    def test_an_empty_list_does_nothing(self, client, db):
        response = client.post("/api/words/known", json={"words": []})

        assert response.status_code == 204
        assert known_words(db) == []
