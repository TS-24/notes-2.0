from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # Argon2 digests are around 100 characters; 255 leaves room to raise the
    # parameters later without a migration.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    notes: Mapped[List["Note"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )
    # Not a cascade. An invite is a record that a code was spent, which stays
    # true after the account it made is gone; only the pointer to that account
    # is released. Without the relationship at all, the leftover foreign key
    # makes deleting any account that registered through the front door a 500.
    invites_used: Mapped[List["InviteCode"]] = relationship(
        back_populates="used_by", foreign_keys="InviteCode.used_by_user_id"
    )
    # The codes this account handed out, and not a cascade either, for the same
    # reason: who let someone in stays true after the person who did it leaves.
    invites_issued: Mapped[List["InviteCode"]] = relationship(
        back_populates="issued_by", foreign_keys="InviteCode.issued_by_user_id"
    )
    # There is no role table and no permission model. This is one flag for the
    # one account that can read the whole invite list and the whole user list,
    # set on the first account created (crud/user.py) because on an empty
    # production database nothing else is in a position to appoint it.
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false(), default=False
    )
    # Both cascades because a foreign key on its own leaves rows pointing at a
    # missing user, which Postgres rejects and SQLite quietly keeps. Deleting an account has to take its conversations and its
    # borrowed credential with it — especially the credential.
    chats: Mapped[List["Chat"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )
    provider_credentials: Mapped[List["ProviderCredential"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    # Which of those credentials is in use, and which of its models. Two columns
    # rather than a flag on the credential or a table of its own: "what am I
    # chatting with" is one fact about the account, and one fact stored once
    # cannot disagree with itself. Null until the first key is saved.
    active_provider: Mapped[Optional[str]] = mapped_column(String(32))
    active_model: Mapped[Optional[str]] = mapped_column(String(128))


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # server_default so rows created outside the ORM still get a timestamp.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Drives "where you left off": the newest-touched note is the one the
    # landing page opens on. Opening a note counts as a touch, so this moves
    # for reads as well as edits.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    # Set when the note is put away, cleared when it is brought back. A
    # timestamp rather than a flag beside is_pinned because it answers both
    # questions the archive asks — whether, and when — and updated_at cannot
    # answer the second: opening a note bumps that, archiving is not a visit.
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped["User"] = relationship(back_populates="notes")
    # Reserved for the hierarchy, and read by nothing yet. It is here so that
    # work is a feature on top of the schema rather than a migration through it
    # — adding a self-reference to a table this central is the expensive half,
    # and doing it now costs one nullable column.
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("notes.id"), nullable=True, index=True
    )

class InviteCode(Base):
    """
    A single-use code that permits one registration.

    Registration is invite-only. Codes come from two places: any signed-in user
    can issue one from their account page, and the CLI can still issue one for
    the case where nobody has an account yet. Redemption is the act of stamping
    `used_at`, so the column doubles as the record of when the code was spent
    and as the thing that stops it being spent twice.
    """

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # The address this code was issued for, folded to lower case, and the
    # account that issued it. Both nullable, and null means the same thing in
    # each: the CLI made this one, before there was anybody to attribute it to
    # or any form to name an address in. A null email is an unbound code that
    # anyone can spend, which is what every code was before this column.
    invited_email: Mapped[Optional[str]] = mapped_column(String(255))
    issued_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    issued_by: Mapped[Optional["User"]] = relationship(
        back_populates="invites_issued", foreign_keys=[issued_by_user_id]
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    used_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    used_by: Mapped[Optional["User"]] = relationship(
        back_populates="invites_used", foreign_keys=[used_by_user_id]
    )


class RevokedToken(Base):
    """
    A token that has been signed out and must no longer be accepted.

    Keyed on the token's own `jti` rather than on the user, so signing out of
    one browser leaves the others alone. Without that distinction the only
    revocation available is "every session this account has", which is not what
    pressing sign out means.

    Rows are disposable: once a token is past its own expiry the signature
    check refuses it regardless, so the record buys nothing and the table would
    grow forever. `expires_at` is kept for exactly that reason — see
    `crud/revoked_token.py::prune_expired`.

    No foreign key to users on purpose. Deleting an account already invalidates
    its tokens, because get_current_user looks the row up, and a cascade here
    would delete the evidence at the moment it stops mattering while adding a
    constraint that can fail.
    """

    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProviderCredential(Base):
    """
    The API key a reader lent us, and which provider it is for.

    The only credential this app holds, and it is held on a *user's* behalf
    rather than the deployment's: it runs on somebody's paid account. So it
    is encrypted at rest (`core/secrets.py`), it never leaves through the
    API, and it is released when the account is. Nothing here runs on a token
    belonging to whoever deployed this — the one thing that did was the word
    ladder's ranker, and it is gone.

    One row per provider per user. A reader who holds keys for two services
    should not have to paste one of them again to go back to it, and the model
    picker in the chat is only worth having if the alternatives are already
    reachable. Which of these rows is in use lives on the user, not here — see
    `User.active_provider`.
    """

    __tablename__ = "provider_credentials"
    # The pair, not the user alone: two rows for the same provider would be two
    # answers to "what is my OpenAI key", and saving a key is an upsert on this.
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_credential_provider"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    user: Mapped["User"] = relationship(back_populates="provider_credentials")
    # A key from the registry in services/llm.py. Not an enum: the set lives in
    # one place already, and a database type would have to be migrated to add a
    # provider that is otherwise one row of a dict.
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # Fernet ciphertext, never the key. Text rather than String(n) because the
    # length follows the key's, and provider key formats are not ours to bound.
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # What this key could reach when it was last asked, which is both the
    # picker's contents and the proof the key worked. Cached rather than fetched
    # per page: a provider call on every chat load would be a spinner, and a
    # provider outage would be an empty picker. Refreshed on demand.
    models: Mapped[Optional[list]] = mapped_column(JSON)
    models_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Chat(Base):
    """
    One conversation with a model, and what was left of it afterwards.

    A chat is a long thing nobody rereads, so what survives it is the summary:
    three parts written when the conversation is finished, which is what the
    chat's card in the library shows from then on.

    `summarized_at` is what "finished" means. A separate status column would be
    a second fact to keep in step with this one, and they would eventually
    disagree.
    """

    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    author: Mapped["User"] = relationship(back_populates="chats")
    # Set from the first thing the reader says; "Untitled" until then, the same
    # placeholder a new note gets.
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Ordering for the library, as with notes: most recently touched first.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # What the conversation came to. Null together, written together — see
    # api/chats.py, which refuses a partial summary rather than storing half.
    #
    # Two columns, not the four this replaces. `general`/`topics`/`questions`/
    # `answers` forced every conversation into a shape two parts of which were
    # about the reader rather than the subject, and nothing ever read them: the
    # durable copy is the prose written into the bound note.
    summary_notes: Mapped[Optional[str]] = mapped_column(Text)
    summary_actions: Mapped[Optional[list]] = mapped_column(JSON)
    summarized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # The note this conversation is bound to, from the moment the conversation
    # exists — not from the moment it is finished, which is what the old
    # `summary_note_id` meant. A note and a chat are two faces of one thing: the
    # note is what a finished conversation is summarised into, and the note's
    # text is what an unfinished one was started from.
    #
    # Unique, so the binding is genuinely one-to-one and a note can never end up
    # with two threads disagreeing about it. Nullable because conversations from
    # before this have no note and are not backfilled; the null path stays
    # supported rather than being guessed at from a migration.
    note_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("notes.id"), unique=True
    )

    # Ordered by id rather than created_at: a question and its answer are
    # written in the same transaction and can share a timestamp, and a
    # transcript that shuffles those two is a different conversation.
    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="ChatMessage.id",
    )


class ChatMessage(Base):
    """One turn. `role` is "user" or "assistant" — see services/llm.py."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), nullable=False, index=True)
    chat: Mapped["Chat"] = relationship(back_populates="messages")
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
