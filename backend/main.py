# pyrefly: ignore [missing-import]
from fastapi import FastAPI, APIRouter, HTTPException
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from contextlib import asynccontextmanager
import textstat
import nltk
from nltk.corpus import wordnet

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Download required NLTK data on startup
    nltk.download('wordnet')
    yield

# Define the FastAPI app
app = FastAPI(
    title="Notes 2.0 API",
    description="Backend API for Notes 2.0 application text analysis",
    version="1.0.0",
    lifespan=lifespan
)

# Set up CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Note Schema
class Note(BaseModel):
    id: str
    title: str
    content: str
    colorId: str
    isPinned: bool
    createdAt: Optional[datetime] = None

# Analysis Response Schema
class AnalysisMetrics(BaseModel):
    wordCount: int
    charCount: int
    # Further metrics (nltk/textstat) will be implemented here later

class AggregateMetrics(BaseModel):
    totalNotes: int
    totalWords: int
    totalChars: int

class NoteInfo(BaseModel):
    id: str
    title: str
    content: str

class VocabularyAnalysis(BaseModel):
    total_difficult_words: int
    definitions: dict[str, str]

class VocabularyResponse(BaseModel):
    note: NoteInfo
    vocabulary_analysis: VocabularyAnalysis

# Router
router = APIRouter(prefix="/api", tags=["notes"])

@router.post("/analyze/note", response_model=AnalysisMetrics)
async def analyze_single_note(note: Note):
    """
    Receives a single Note object, processes the text content, and returns basic metrics.
    """
    word_count = len(note.content.split())
    char_count = len(note.content)
    
    return AnalysisMetrics(
        wordCount=word_count,
        charCount=char_count
    )

@router.post("/analyze/aggregate", response_model=AggregateMetrics)
async def analyze_aggregate(notes: List[Note]):
    """
    Receives an array of Note objects and returns aggregated metrics.
    """
    total_notes = len(notes)
    total_words = sum(len(note.content.split()) for note in notes)
    total_chars = sum(len(note.content) for note in notes)
    
    return AggregateMetrics(
        totalNotes=total_notes,
        totalWords=total_words,
        totalChars=total_chars
    )

@router.post("/analyze/vocabulary", response_model=VocabularyResponse)
async def analyze_vocabulary(note: Note):
    """
    Ingests a user's text note, identifies complex vocabulary,
    looks up definitions, and returns a strictly structured JSON response.
    """
    # 1. Extraction
    difficult_words = textstat.difficult_words_list(note.content)
    
    # 2. Normalization
    normalized_words = list(set([word.lower().strip() for word in difficult_words]))
    
    # 3. Definition Lookup
    definitions = {}
    for word in normalized_words:
        synsets = wordnet.synsets(word)
        if synsets:
            # Extract the .definition() of the first primary synset
            definitions[word] = synsets[0].definition()
        else:
            # Fallback
            definitions[word] = "Definition not found in database."
            
    # 4. Data Packaging
    return VocabularyResponse(
        note=NoteInfo(
            id=note.id,
            title=note.title,
            content=note.content
        ),
        vocabulary_analysis=VocabularyAnalysis(
            total_difficult_words=len(definitions),
            definitions=definitions
        )
    )

@router.get("/health")
async def health_check():
    """
    Simple health check endpoint to verify backend status.
    """
    return {"status": "ok"}

# Register router
app.include_router(router)

if __name__ == "__main__":
    # pyrefly: ignore [missing-import]
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
