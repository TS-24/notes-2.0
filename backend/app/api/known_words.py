from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..crud import known_word as crud_known
from ..db.database import get_db
from ..db.models import User
from ..schemas.known_word import KnownWordsCreate
from .deps import get_current_user

# Shares the /words prefix with word_definitions. Registration order matters:
# that router has a GET /{word_id} typed as an int, so if it went first the
# path "known" would be parsed as an id and rejected as a 422 rather than
# reaching this route.
router = APIRouter(prefix="/words", tags=["words"])


@router.post("/known", status_code=status.HTTP_204_NO_CONTENT)
def mark_words_known(
    payload: KnownWordsCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """
    Record that the user already knows these words.

    No body comes back. The note grid removes the card before this request is
    sent and never reads the response — there is nothing it could do with one,
    and a 409 on a duplicate would only produce a console error for something
    the user has already successfully done.
    """
    crud_known.add_known_words(db, user_id=user.id, words=payload.words)
