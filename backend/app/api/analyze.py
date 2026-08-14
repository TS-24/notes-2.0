from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..crud import known_word as crud_known
from ..db.database import get_db
from ..db.models import User
from ..schemas.analyze import (
    VocabularyAnalysis,
    VocabularyAnalysisRequest,
    VocabularyAnalysisResponse,
)
from ..services.analysis import difficult_words
from .deps import get_current_user

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("/vocabulary", response_model=VocabularyAnalysisResponse)
def analyze_vocabulary(
    payload: VocabularyAnalysisRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VocabularyAnalysisResponse:
    """
    The words in this text worth learning, with their definitions.

    Called two ways: the analytics page sends every note joined together, and
    the note grid sends a single note. Same answer either way — the text is
    treated as one body regardless of where it came from.

    Words the user has already dismissed are left out, so the list shrinks as
    they work through it rather than showing the same words on every visit.
    """
    known = crud_known.list_known_words(db, user_id=user.id)
    definitions = difficult_words(payload.content, known=known)
    return VocabularyAnalysisResponse(
        vocabulary_analysis=VocabularyAnalysis(
            total_difficult_words=len(definitions),
            definitions=definitions,
        )
    )
