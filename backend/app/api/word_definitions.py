from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..crud import word_definition as crud_word
from ..db.database import get_db
from ..schemas.word_definition import (
    WordDefinitionCreate,
    WordDefinitionRead,
    WordDefinitionUpdate,
)

router = APIRouter(prefix="/words", tags=["words"])


@router.post("", response_model=WordDefinitionRead, status_code=status.HTTP_201_CREATED)
def create_word_definition(
    payload: WordDefinitionCreate, db: Session = Depends(get_db)
) -> WordDefinitionRead:
    return crud_word.create_word_definition(
        db, word=payload.word, definition=payload.definition
    )


@router.get("", response_model=list[WordDefinitionRead])
def list_word_definitions(
    word: str | None = Query(None, description="Look up an exact word instead of paging"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[WordDefinitionRead]:
    if word is not None:
        match = crud_word.get_word_definition_by_word(db, word)
        return [match] if match is not None else []
    return crud_word.list_word_definitions(db, skip=skip, limit=limit)


@router.get("/{word_id}", response_model=WordDefinitionRead)
def get_word_definition(word_id: int, db: Session = Depends(get_db)) -> WordDefinitionRead:
    word_definition = crud_word.get_word_definition(db, word_id)
    if word_definition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Word definition not found"
        )
    return word_definition


@router.patch("/{word_id}", response_model=WordDefinitionRead)
def update_word_definition(
    word_id: int, payload: WordDefinitionUpdate, db: Session = Depends(get_db)
) -> WordDefinitionRead:
    word_definition = crud_word.update_word_definition(
        db, word_id, **payload.model_dump(exclude_unset=True)
    )
    if word_definition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Word definition not found"
        )
    return word_definition


@router.delete("/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_word_definition(word_id: int, db: Session = Depends(get_db)) -> None:
    if not crud_word.delete_word_definition(db, word_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Word definition not found"
        )
