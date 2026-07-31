from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..crud import note as crud_note
from ..crud import user as crud_user
from ..crud import word_definition as crud_word
from ..db.database import get_db
from ..db.models import User
from ..schemas.note import NoteCreate, NoteRead, NoteUpdate
from .deps import get_current_user

router = APIRouter(prefix="/notes", tags=["notes"])


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    user_id = payload.user_id if payload.user_id is not None else current_user.id
    if crud_user.get_user(db, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return crud_note.create_note(
        db, user_id=user_id, title=payload.title, content=payload.content
    )


@router.get("", response_model=list[NoteRead])
def list_notes(
    user_id: int | None = None,
    search: str | None = Query(None, description="Case-insensitive match on note title"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[NoteRead]:
    return crud_note.list_notes(db, user_id=user_id, search=search, skip=skip, limit=limit)


@router.get("/{note_id}", response_model=NoteRead)
def get_note(note_id: int, db: Session = Depends(get_db)) -> NoteRead:
    note = crud_note.get_note(db, note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.patch("/{note_id}", response_model=NoteRead)
def update_note(note_id: int, payload: NoteUpdate, db: Session = Depends(get_db)) -> NoteRead:
    note = crud_note.update_note(db, note_id, **payload.model_dump(exclude_unset=True))
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.post("/{note_id}/touch", response_model=NoteRead)
def touch_note(note_id: int, db: Session = Depends(get_db)) -> NoteRead:
    """Record that a note was opened, so it becomes 'where you left off'."""
    note = crud_note.touch_note(db, note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, db: Session = Depends(get_db)) -> None:
    if not crud_note.delete_note(db, note_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")


@router.post("/{note_id}/words/{word_id}", response_model=NoteRead)
def add_word_to_note(note_id: int, word_id: int, db: Session = Depends(get_db)) -> NoteRead:
    _assert_note_and_word_exist(db, note_id, word_id)
    note = crud_note.add_word_to_note(db, note_id, word_id)
    assert note is not None
    return note


@router.delete("/{note_id}/words/{word_id}", response_model=NoteRead)
def remove_word_from_note(note_id: int, word_id: int, db: Session = Depends(get_db)) -> NoteRead:
    _assert_note_and_word_exist(db, note_id, word_id)
    note = crud_note.remove_word_from_note(db, note_id, word_id)
    assert note is not None
    return note


def _assert_note_and_word_exist(db: Session, note_id: int, word_id: int) -> None:
    """Raise a 404 naming whichever of the two rows is missing."""
    if crud_note.get_note(db, note_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    if crud_word.get_word_definition(db, word_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Word definition not found"
        )
