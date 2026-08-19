"""
Tests that one account cannot reach another's notes (app/api/notes.py).

Every case here failed before the routes were scoped: the note routes looked a
note up by id and never asked who was asking, so any id was readable, editable
and deletable by anyone.

Two things are asserted rather than one. The status code says the request was
refused, and a second assertion says the row is unchanged — because the
refusal used to be written after the write, and a test that only reads the
status code passes just as happily against code that mutated first and
apologised afterwards.

The refusal is 404 rather than 403 throughout. 403 would confirm the note
exists, which turns the id space into a directory of other people's writing.
"""

from sqlalchemy import select

from app.db.models import Note


def note_of(db, user, title: str = "Theirs", content: str = "Private") -> Note:
    note = Note(user_id=user.id, title=title, content=content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


class TestReadingSomeoneElsesNote:
    def test_getting_it_is_a_404(self, client, db, other_user):
        theirs = note_of(db, other_user)

        assert client.get(f"/api/notes/{theirs.id}").status_code == 404

    def test_the_listing_only_holds_my_own(self, client, db, user, other_user):
        note_of(db, other_user, title="Theirs")
        note_of(db, user, title="Mine")

        titles = [n["title"] for n in client.get("/api/notes").json()]

        assert titles == ["Mine"]

    def test_a_user_id_query_param_cannot_widen_the_listing(self, client, db, other_user):
        # The param used to exist and defaulted to every user's notes.
        note_of(db, other_user)

        body = client.get(f"/api/notes?user_id={other_user.id}").json()

        assert body == []


class TestWritingToSomeoneElsesNote:
    def test_patching_it_is_a_404_and_changes_nothing(self, client, db, other_user):
        theirs = note_of(db, other_user)

        response = client.patch(f"/api/notes/{theirs.id}", json={"title": "Defaced"})

        assert response.status_code == 404
        db.expire_all()
        assert db.get(Note, theirs.id).title == "Theirs"

    def test_touching_it_is_a_404_and_does_not_move_it(self, client, db, other_user):
        theirs = note_of(db, other_user)
        before = theirs.updated_at

        response = client.post(f"/api/notes/{theirs.id}/touch")

        assert response.status_code == 404
        db.expire_all()
        assert db.get(Note, theirs.id).updated_at == before

    def test_deleting_it_is_a_404_and_leaves_it_there(self, client, db, other_user):
        theirs = note_of(db, other_user)

        response = client.delete(f"/api/notes/{theirs.id}")

        assert response.status_code == 404
        assert db.get(Note, theirs.id) is not None

    def test_pinning_it_is_a_404(self, client, db, other_user):
        theirs = note_of(db, other_user)

        response = client.patch(f"/api/notes/{theirs.id}", json={"is_pinned": True})

        assert response.status_code == 404
        db.expire_all()
        assert db.get(Note, theirs.id).is_pinned is False


class TestOwnership:
    def test_a_new_note_belongs_to_the_caller(self, client, db, user):
        client.post("/api/notes", json={"title": "Mine"})

        assert db.scalars(select(Note)).one().user_id == user.id

    def test_a_user_id_in_the_body_cannot_hand_the_note_to_someone_else(
        self, client, db, user, other_user
    ):
        # The field is gone from the schema, so this is checking that pydantic
        # ignores it rather than that the route defends against it.
        client.post("/api/notes", json={"title": "Mine", "user_id": other_user.id})

        assert db.scalars(select(Note)).one().user_id == user.id

    def test_my_own_note_is_readable(self, client, db, user):
        mine = note_of(db, user, title="Mine")

        response = client.get(f"/api/notes/{mine.id}")

        assert response.status_code == 200
        assert response.json()["title"] == "Mine"


class TestWithoutCredentials:
    def test_every_note_route_refuses(self, anon_client, db, user):
        mine = note_of(db, user)

        assert anon_client.get("/api/notes").status_code == 401
        assert anon_client.post("/api/notes", json={"title": "x"}).status_code == 401
        assert anon_client.get(f"/api/notes/{mine.id}").status_code == 401
        assert anon_client.patch(f"/api/notes/{mine.id}", json={"title": "x"}).status_code == 401
        assert anon_client.post(f"/api/notes/{mine.id}/touch").status_code == 401
        assert anon_client.delete(f"/api/notes/{mine.id}").status_code == 401
