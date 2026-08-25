"""
Chats and their turns.

Same ownership discipline as crud/note.py: `user_id` is a required argument, not
an optional filter, so a forgotten one is a TypeError rather than a query that
quietly means "any user". Every lookup goes through `get_chat`, so there is one
place where ownership is decided.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db.models import Chat, ChatMessage, Note

# What a chat is called before anything has been said in it.
#
# Notes no longer store this: theirs is placeholder text in the field and the
# column holds "". A chat still writes it, because its title is shown in its
# own surface rather than beside a note's. Both spellings of "unnamed" are
# therefore live, which is why the checks below test for either.
UNTITLED = "Untitled"


def create_chat(
    db: Session, user_id: int, note_id: int, seed: str | None = None
) -> Chat:
    """Start a conversation bound to a note, optionally seeded from its text.

    The binding is required, not optional: every chat has a note, and the one
    place chats are born is the one place that can be true. The caller supplies
    the note — either the one the reader started from, or one made for the
    occasion.

    `seed` is stored as a `system` turn, which is the note's text at the moment
    the conversation began. It is written once here and never rewritten: opening
    the chat again is opening a conversation that already has a history, not
    starting it over from a note that has since moved on.
    """
    chat = Chat(user_id=user_id, title=UNTITLED, note_id=note_id)
    if seed:
        chat.messages.append(ChatMessage(role="system", content=seed))
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def chat_for_note(db: Session, note_id: int, user_id: int) -> Chat | None:
    """This note's conversation, if it has one. The binding is one-to-one."""
    stmt = (
        select(Chat)
        .where(Chat.note_id == note_id, Chat.user_id == user_id)
        .options(selectinload(Chat.messages))
    )
    return db.scalars(stmt).first()


def get_chat(db: Session, chat_id: int, user_id: int) -> Chat | None:
    """One of this user's chats, with its turns. None if missing or not theirs.

    The two are not distinguished, for the reason notes give: a different answer
    would confirm that a chat exists and belongs to somebody else, turning the
    id space into a directory of other people's conversations.
    """
    stmt = (
        select(Chat)
        .where(Chat.id == chat_id, Chat.user_id == user_id)
        .options(selectinload(Chat.messages))
    )
    return db.scalars(stmt).first()


def list_chats(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> list[Chat]:
    """A page of one user's chats, most recently touched first."""
    stmt = (
        select(Chat)
        .options(selectinload(Chat.messages))
        .where(Chat.user_id == user_id)
        # Same ordering as notes, and id breaks ties between rows written in the
        # same transaction.
        .order_by(Chat.updated_at.desc(), Chat.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt))


def rename_chat(db: Session, chat_id: int, user_id: int, title: str) -> Chat | None:
    """Give one of this user's chats a new name. None if it is not theirs.

    `updated_at` is left alone deliberately. It orders the library by what you
    were working on, and correcting a name is not working on the conversation —
    a rename that moved a year-old chat to the head of the grid would be the
    ordering lying about what you had been doing.
    """
    chat = get_chat(db, chat_id, user_id)
    if chat is None:
        return None

    chat.title = title
    db.commit()
    db.refresh(chat)
    return chat


def delete_chat(db: Session, chat_id: int, user_id: int) -> bool:
    """Delete one of this user's chats and its turns; True if a row went."""
    chat = get_chat(db, chat_id, user_id)
    if chat is None:
        return False

    db.delete(chat)
    db.commit()
    return True


def add_exchange(db: Session, chat: Chat, question: str, answer: str) -> Chat:
    """
    Store a question and its answer together, in one transaction.

    Together on purpose. If the reader's turn were committed before the provider
    was called, a provider that refused would leave a transcript ending on an
    unanswered question — which the next request would resend and the summary
    would have to describe. The caller therefore gets the answer first and only
    then arrives here.
    """
    chat.messages.append(ChatMessage(role="user", content=question))
    chat.messages.append(ChatMessage(role="assistant", content=answer))

    if chat.title == UNTITLED:
        chat.title = title_from(question)
        # And the note it is bound to, when that has no name either. A
        # conversation started from the library makes an Untitled note to end up
        # in, so closing it would otherwise land the reader on a blank page with
        # nothing on it to say what it was. A note the reader named, or one a
        # conversation was started *from*, already says what it is and is left
        # alone.
        note = _bound_note(db, chat)
        if note is not None and note.title.strip() in ("", UNTITLED):
            note.title = chat.title

    # Talking again takes a finished conversation up where it left off, so it is
    # not finished any more and the summary describing it has to go. Nothing is
    # lost: every part of it was written into the note as text when the chat was
    # finished, and the note keeps that until the next finish rewrites it.
    if chat.summarized_at is not None:
        _forget_summary(chat)

    # Explicitly, for the reason touch_note gives: appending to a relationship
    # does not dirty the parent's own columns, so `onupdate` would not fire and
    # the chat would never move to the head of the library.
    chat.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(chat)
    return chat


def _bound_note(db: Session, chat: Chat) -> Note | None:
    """The note this conversation is two faces of, or None for an old one.

    Scoped by owner as well as by id, for the reason every lookup here is: an
    unscoped filter is one forgotten argument away from meaning "any user".
    """
    if chat.note_id is None:
        return None
    stmt = select(Note).where(Note.id == chat.note_id, Note.user_id == chat.user_id)
    return db.scalars(stmt).first()


def _forget_summary(chat: Chat) -> None:
    """Put a chat back to being unfinished. The inverse of `store_summary`.

    All three columns together, as they are written — a chat holding notes and
    no `summarized_at` is a state the schema permits and nothing should create.
    """
    chat.summary_notes = None
    chat.summary_actions = None
    chat.summarized_at = None


def title_from(question: str) -> str:
    """A chat's name, taken from the first thing said in it.

    Trimmed to fit the column with room to spare. Cut at a word boundary where
    there is one near the end, because a title severed mid-word reads as a bug
    rather than as an abbreviation.
    """
    text = " ".join(question.split())
    if len(text) <= 80:
        return text

    cut = text[:80]
    spaced = cut.rsplit(" ", 1)[0]
    return f"{spaced if len(spaced) > 40 else cut}…"


def store_summary(db: Session, chat: Chat, summary) -> Chat:
    """
    Write the whole summary, or none of it.

    One assignment block and one commit: a chat holding notes with no
    `summarized_at` is a state the schema permits and nothing should create.

    An empty `actions` list is stored as an empty list rather than as null. It
    is the ordinary answer — most conversations imply nothing to do — and null
    would make "no actions" indistinguishable from "never summarised".

    Nothing here touches `note_id`: the note this was written into was decided
    when the conversation started, not now.
    """
    chat.summary_notes = summary.notes
    chat.summary_actions = list(summary.actions)
    chat.summarized_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(chat)
    return chat
