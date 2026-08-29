from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


note_word_association = Table(
    "note_word",
    Base.metadata,
    Column("note_id", ForeignKey("notes.id"), primary_key=True),
    Column("word_id", ForeignKey("word_definitions.id"), primary_key=True),
)


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
    # Set the moment a password is reset. A token whose `iat` predates this is
    # refused by get_current_user, so resetting a compromised account also ends
    # every session it already had. NULL means the password has never been
    # reset, which is every account until it uses the flow.
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[List["Note"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )
    # Deleting an account has to take its known words with it. The foreign key
    # alone does not do that: it would leave rows pointing at a missing user,
    # which Postgres rejects and SQLite quietly keeps.
    known_words: Mapped[List["KnownWord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    # Not a cascade. An invite is a record that a code was spent, which stays
    # true after the account it made is gone; only the pointer to that account
    # is released. Without the relationship at all, the leftover foreign key
    # makes deleting any account that registered through the front door a 500.
    invites_used: Mapped[List["InviteCode"]] = relationship(back_populates="used_by")
    # Both cascades for the same reason as known_words: a foreign key on its own
    # leaves rows pointing at a missing user, which Postgres rejects and SQLite
    # quietly keeps. Deleting an account has to take its conversations and its
    # borrowed credential with it — especially the credential.
    chats: Mapped[List["Chat"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )
    provider_credential: Mapped[Optional["ProviderCredential"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


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
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped["User"] = relationship(back_populates="notes")

    words: Mapped[List["WordDefinition"]] = relationship(
        secondary=note_word_association, back_populates="notes"
    )


class WordDefinition(Base):
    __tablename__ = "word_definitions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(255), nullable=False)
    definition: Mapped[Optional[str]] = mapped_column(Text)

    notes: Mapped[List["Note"]] = relationship(
        secondary=note_word_association, back_populates="words"
    )


class WordLadder(Base):
    """
    A cached word ladder — see app/services/vocab.py.

    Building one means walking WordNet and scoring every candidate, which is
    the same answer every time for the same word, so it is worth computing once
    for everybody rather than once per keystroke.

    Keyed on the *surface* form, not the lemma: the rungs are inflected to match
    what was asked about, so "run" and "running" are legitimately separate rows.
    """

    # `pos` is the part of speech the ladder was *resolved* to, not a lookup
    # key — the caller does not say which one they meant, so the service picks.

    __tablename__ = "word_ladders"
    __table_args__ = (
        UniqueConstraint("word", "context_hash", name="uq_word_ladders_word_context"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Which sentence the ladder was built for, hashed — empty when the ranker is
    # off, since a dictionary ladder depends on nothing but the word. This is
    # the price of context: the answer stops being a property of the word, so
    # the cache converges on sentences rather than on vocabulary.
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    pos: Mapped[str] = mapped_column(String(2), nullable=False, server_default="")
    # The rungs in order, plainest first.
    rungs: Mapped[list] = mapped_column(JSON, nullable=False)
    origin_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KnownWord(Base):
    """
    A word the user has said they already know.

    Kept per user rather than globally: "difficult" is a fact about a reader,
    not about a word, and the whole point of dismissing one is that this reader
    is done being shown it.

    Stored as the surface form the analysis offered, because that is what the
    user was actually looking at when they dismissed it. Lemmatising here would
    quietly dismiss "running" along with "run", which is a bigger claim than
    the user made.
    """

    __tablename__ = "known_words"
    __table_args__ = (
        UniqueConstraint("user_id", "word", name="uq_known_words_user_word"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    user: Mapped["User"] = relationship(back_populates="known_words")
    word: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InviteCode(Base):
    """
    A single-use code that permits one registration.

    Registration is invite-only, and these are issued by hand from the CLI:
    there is no self-service. Redemption is the act of stamping `used_at`, so
    the column doubles as the record of when the code was spent and as the
    thing that stops it being spent twice.
    """

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    used_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    used_by: Mapped[Optional["User"]] = relationship(back_populates="invites_used")


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


class PasswordResetToken(Base):
    """
    A one-time token that authorises a single password reset.

    Only the SHA-256 of the token is stored; the token itself exists only in
    the link that was emailed, the same arrangement a password has with its
    hash. `used_at` is both the record that a reset happened and the thing that
    stops the link working twice — the shape `InviteCode` uses for that job.

    No foreign key to users, for the reason `RevokedToken` gives: deleting an
    account must not be gated on clearing rows that stop mattering the moment it
    is gone. Expired and used rows are disposable — see
    `crud/password_reset.py::prune_expired`.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    # SHA-256 hex of the emailed token: 64 characters exactly. Unique, so a
    # replay cannot resolve to a second row.
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    # Indexed for pruning — the CLI sweeps every row past its expiry.
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProviderCredential(Base):
    """
    The API key a reader lent us, and which provider it is for.

    The first credential this app holds on a *user's* behalf rather than the
    deployment's — the word ladder's model runs on the deployment's own token,
    this runs on somebody's paid account. So it is encrypted at rest
    (`core/secrets.py`), it never leaves through the API, and it is released
    when the account is.

    One row per user rather than one per provider. "Which provider do you use"
    is the question the settings page asks, and a set of stored keys with an
    active flag would be a second thing to keep in step with the first for no
    behaviour anyone asked for. Saving a different provider replaces the row.
    """

    __tablename__ = "provider_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    user: Mapped["User"] = relationship(back_populates="provider_credential")
    # A key from the registry in services/llm.py. Not an enum: the set lives in
    # one place already, and a database type would have to be migrated to add a
    # provider that is otherwise one row of a dict.
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # Fernet ciphertext, never the key. Text rather than String(n) because the
    # length follows the key's, and provider key formats are not ours to bound.
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # An override for the provider's default model. Null means "whatever
    # services/llm.py currently defaults to", which is what lets a stale default
    # be fixed by editing that file rather than every row here.
    model: Mapped[Optional[str]] = mapped_column(String(128))
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

    # The three parts. Null together, written together — see api/chats.py, which
    # refuses a partial summary rather than storing a third of one.
    summary_general: Mapped[Optional[str]] = mapped_column(Text)
    summary_topics: Mapped[Optional[list]] = mapped_column(JSON)
    summary_questions: Mapped[Optional[str]] = mapped_column(Text)
    summary_answers: Mapped[Optional[str]] = mapped_column(Text)
    summarized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

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
