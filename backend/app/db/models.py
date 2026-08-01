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
    notes: Mapped[List["Note"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
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
    # Which sentence the ladder was built for, hashed — empty for the WordNet
    # engine, which never sees one. This is the cost of a contextual engine: the
    # answer is no longer a property of the word, so the cache converges on the
    # set of *sentences* a person writes rather than the set of words.
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    pos: Mapped[str] = mapped_column(String(2), nullable=False, server_default="")
    # The rungs in order, plainest first.
    rungs: Mapped[list] = mapped_column(JSON, nullable=False)
    origin_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
