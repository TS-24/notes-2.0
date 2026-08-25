"""
A note that was never written in goes away, and the rest can be archived.

Two features that share a definition. `Untitled` used to be written into the
database as a real title, so a note the app made on your behalf and you never
touched was not empty — it was a note *called* "Untitled" with no body, and it
stood in the library until you deleted it by hand. Now the placeholder stays in
the markup and the column holds `""`, which is what makes "blank" a thing the
server can recognise at all.

Blank is `not title.strip() and not content.strip()`. Deliberately no special
case for the string "Untitled": notes already carrying it as a real title are
left alone, and a reader who types that word has named their note.

Archiving is the other half — the reversible one, for notes that do have
something in them.
"""

import pytest
from sqlalchemy import select

from app.crud import note as crud_note
from app.db.models import Chat, ChatMessage, Note


def make_note(db, user, title: str = "", content: str = "") -> Note:
    note = Note(user_id=user.id, title=title, content=content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def bind_chat(db, user, note: Note, *, said: str | None = None) -> Chat:
    """A conversation on a note, optionally one that got somewhere."""
    chat = Chat(user_id=user.id, title="Untitled", note_id=note.id)
    if said is not None:
        chat.messages.append(ChatMessage(role="user", content=said))
        chat.messages.append(ChatMessage(role="assistant", content="a reply"))
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


class TestAnEmptyTitleIsAllowed:
    """The schema required one character, which is what forced the fallback."""

    def test_a_note_can_be_created_with_no_title(self, client):
        response = client.post("/api/notes", json={"title": "", "content": ""})

        assert response.status_code == 201
        assert response.json()["title"] == ""

    def test_a_title_can_be_cleared(self, client, db, user):
        note = make_note(db, user, title="Named", content="Words.")

        response = client.patch(f"/api/notes/{note.id}", json={"title": ""})

        assert response.status_code == 200
        assert response.json()["title"] == ""


class TestClosingABlankNote:
    """`close` is the reader leaving the note, which is when it is judged."""

    def test_a_blank_note_is_deleted(self, client, db, user):
        keeper = make_note(db, user, title="Keeper", content="Something.")
        blank = make_note(db, user)

        response = client.post(f"/api/notes/{blank.id}/close")

        assert response.status_code == 204
        db.expire_all()
        assert db.get(Note, blank.id) is None
        assert db.get(Note, keeper.id) is not None

    def test_whitespace_alone_is_still_blank(self, client, db, user):
        make_note(db, user, title="Keeper", content="Something.")
        blank = make_note(db, user, title="   ", content="\n\t ")

        assert client.post(f"/api/notes/{blank.id}/close").status_code == 204
        db.expire_all()
        assert db.get(Note, blank.id) is None

    def test_a_note_with_a_title_survives(self, client, db, user):
        make_note(db, user, title="Keeper", content="Something.")
        named = make_note(db, user, title="Groceries")

        response = client.post(f"/api/notes/{named.id}/close")

        assert response.status_code == 200
        db.expire_all()
        assert db.get(Note, named.id) is not None

    def test_a_note_with_a_body_survives(self, client, db, user):
        make_note(db, user, title="Keeper", content="Something.")
        bodied = make_note(db, user, content="Flour, water, salt.")

        assert client.post(f"/api/notes/{bodied.id}/close").status_code == 200
        db.expire_all()
        assert db.get(Note, bodied.id) is not None

    def test_a_note_titled_untitled_is_not_blank(self, client, db, user):
        """The old rows keep their real title, and a real title is a title."""
        make_note(db, user, title="Keeper", content="Something.")
        old = make_note(db, user, title="Untitled")

        assert client.post(f"/api/notes/{old.id}/close").status_code == 200
        db.expire_all()
        assert db.get(Note, old.id) is not None

    def test_the_only_note_survives_even_when_blank(self, client, db, user):
        """
        The app has no empty state.

        `routes/workspace.tsx` creates a note when the list comes back empty,
        precisely so the landing page is never blank — so deleting the last one
        just makes it make another.
        """
        only = make_note(db, user)

        assert client.post(f"/api/notes/{only.id}/close").status_code == 200
        db.expire_all()
        assert db.get(Note, only.id) is not None

    def test_closing_someone_elses_note_is_a_404(self, client, db, other_user):
        make_note(db, other_user, title="Keeper", content="Something.")
        theirs = make_note(db, other_user)

        assert client.post(f"/api/notes/{theirs.id}/close").status_code == 404
        db.expire_all()
        assert db.get(Note, theirs.id) is not None


class TestClosingABlankNoteThatHasAConversation:
    def test_a_chat_with_nothing_said_goes_with_it(self, client, db, user):
        """"New AI chat" makes a note to end up in. Say nothing and both go."""
        make_note(db, user, title="Keeper", content="Something.")
        blank = make_note(db, user)
        chat = bind_chat(db, user, blank)

        assert client.post(f"/api/notes/{blank.id}/close").status_code == 204
        db.expire_all()
        assert db.get(Note, blank.id) is None
        assert db.get(Chat, chat.id) is None

    def test_a_chat_that_got_somewhere_keeps_its_note(self, client, db, user):
        """The transcript is the note's content even when the body is empty."""
        make_note(db, user, title="Keeper", content="Something.")
        blank = make_note(db, user)
        chat = bind_chat(db, user, blank, said="what is a gerund?")

        assert client.post(f"/api/notes/{blank.id}/close").status_code == 200
        db.expire_all()
        assert db.get(Note, blank.id) is not None
        assert db.get(Chat, chat.id) is not None


class TestDeletingANoteThatHasAConversation:
    """
    A regression. `Chat.note_id` is a foreign key with no `ondelete` and `Note`
    has no relationship back, so deleting a chat-bound note used to raise an
    IntegrityError on Postgres — the Trash button on any note you had talked
    about. Orphaning the chat instead is not the fix: the library holds notes
    only, so a chat with no note is a chat with no way in.
    """

    def test_the_chat_goes_with_the_note(self, client, db, user):
        note = make_note(db, user, title="Gerunds", content="A verb as a noun.")
        chat = bind_chat(db, user, note, said="what is a gerund?")

        assert client.delete(f"/api/notes/{note.id}").status_code == 204
        db.expire_all()
        assert db.get(Note, note.id) is None
        assert db.get(Chat, chat.id) is None

    def test_its_messages_go_too(self, client, db, user):
        note = make_note(db, user, title="Gerunds", content="A verb as a noun.")
        bind_chat(db, user, note, said="what is a gerund?")

        client.delete(f"/api/notes/{note.id}")

        db.expire_all()
        assert db.scalars(select(ChatMessage)).all() == []


class TestArchiving:
    def test_a_note_can_be_archived_and_leaves_the_listing(self, client, db, user):
        note = make_note(db, user, title="Recipes", content="Flour.")

        response = client.post(f"/api/notes/{note.id}/archive")

        assert response.status_code == 200
        assert response.json()["archived_at"] is not None
        assert [n["id"] for n in client.get("/api/notes").json()] == []

    def test_the_archived_listing_holds_it(self, client, db, user):
        note = make_note(db, user, title="Recipes", content="Flour.")
        client.post(f"/api/notes/{note.id}/archive")

        listed = client.get("/api/notes?archived=true").json()

        assert [n["id"] for n in listed] == [note.id]

    def test_restoring_puts_it_back(self, client, db, user):
        note = make_note(db, user, title="Recipes", content="Flour.")
        client.post(f"/api/notes/{note.id}/archive")

        response = client.post(f"/api/notes/{note.id}/unarchive")

        assert response.status_code == 200
        assert response.json()["archived_at"] is None
        assert [n["id"] for n in client.get("/api/notes").json()] == [note.id]
        assert client.get("/api/notes?archived=true").json() == []

    def test_the_last_note_can_be_archived_by_hand(self, client, db, user):
        """The guard is on the automatic rule only; this one you asked for."""
        only = make_note(db, user, title="Recipes", content="Flour.")

        assert client.post(f"/api/notes/{only.id}/archive").status_code == 200

    def test_the_newest_archived_comes_first(self, client, db, user):
        first = make_note(db, user, title="First", content="a")
        second = make_note(db, user, title="Second", content="b")
        client.post(f"/api/notes/{first.id}/archive")
        client.post(f"/api/notes/{second.id}/archive")

        listed = client.get("/api/notes?archived=true").json()

        assert [n["title"] for n in listed] == ["Second", "First"]

    @pytest.mark.parametrize("action", ["archive", "unarchive"])
    def test_doing_it_to_someone_elses_note_is_a_404(self, client, db, other_user, action):
        theirs = make_note(db, other_user, title="Theirs", content="Private.")

        assert client.post(f"/api/notes/{theirs.id}/{action}").status_code == 404
        db.expire_all()
        assert db.get(Note, theirs.id).archived_at is None


class TestTheCrudRuleItself:
    """`list_notes` is called directly here: the default is the load-bearing bit."""

    def test_archived_notes_are_excluded_by_default(self, db, user):
        kept = make_note(db, user, title="Kept", content="a")
        gone = make_note(db, user, title="Gone", content="b")
        crud_note.archive_note(db, gone.id, user.id)

        assert [n.id for n in crud_note.list_notes(db, user.id)] == [kept.id]

    def test_a_search_does_not_reach_into_the_archive(self, db, user):
        note = make_note(db, user, title="Recipes", content="a")
        crud_note.archive_note(db, note.id, user.id)

        assert crud_note.list_notes(db, user.id, search="Recipes") == []
