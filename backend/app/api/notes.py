from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..crud import note as crud_note
from ..crud import word_definition as crud_word
from ..db.database import get_db
from ..db.models import Note, User
from ..schemas.note import NoteCreate, NoteRead, NoteUpdate
from .deps import get_current_user

router = APIRouter(prefix="/notes", tags=["notes"])

# A note that belongs to someone else answers exactly like one that does not
# exist. 403 would be more precise and worse: it confirms the note is real,
# which makes the id space a directory of other people's writing.
NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")


def _owned_note(db: Session, note_id: int, user: User) -> Note:
    """This user's note, or a 404.

    Called before anything is written, never after. The refusal used to come
    after the update, which meant another user's row was already modified by
    the time the request was turned down.
    """
    note = crud_note.get_note(db, note_id, user.id)
    if note is None:
        raise NOT_FOUND
    return note


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    return crud_note.create_note(
        db, user_id=current_user.id, title=payload.title, content=payload.content
    )


@router.get("", response_model=list[NoteRead])
def list_notes(
    search: str | None = Query(None, description="Case-insensitive match on note title"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NoteRead]:
    return crud_note.list_notes(
        db, user_id=current_user.id, search=search, skip=skip, limit=limit
    )


@router.get("/{note_id}", response_model=NoteRead)
def get_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    return _owned_note(db, note_id, current_user)


@router.patch("/{note_id}", response_model=NoteRead)
def update_note(
    note_id: int,
    payload: NoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    note = crud_note.update_note(
        db, note_id, current_user.id, **payload.model_dump(exclude_unset=True)
    )
    if note is None:
        raise NOT_FOUND
    return note


@router.post("/{note_id}/touch", response_model=NoteRead)
def touch_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    """Record that a note was opened, so it becomes 'where you left off'."""
    note = crud_note.touch_note(db, note_id, current_user.id)
    if note is None:
        raise NOT_FOUND
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if not crud_note.delete_note(db, note_id, current_user.id):
        raise NOT_FOUND


@router.post("/{note_id}/words/{word_id}", response_model=NoteRead)
def add_word_to_note(
    note_id: int,
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    _assert_word_exists(db, word_id)
    _owned_note(db, note_id, current_user)
    note = crud_note.add_word_to_note(db, note_id, word_id, current_user.id)
    assert note is not None
    return note


@router.delete("/{note_id}/words/{word_id}", response_model=NoteRead)
def remove_word_from_note(
    note_id: int,
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    _assert_word_exists(db, word_id)
    _owned_note(db, note_id, current_user)
    note = crud_note.remove_word_from_note(db, note_id, word_id, current_user.id)
    assert note is not None
    return note


def _assert_word_exists(db: Session, word_id: int) -> None:
    """Word definitions are shared across every note, so they have no owner."""
    if crud_word.get_word_definition(db, word_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Word definition not found"
        )
