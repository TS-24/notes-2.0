from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# Define the FastAPI app
app = FastAPI(
    title="Notes 2.0 API",
    description="Backend API for Notes 2.0 application text analysis",
    version="1.0.0"
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

@router.get("/health")
async def health_check():
    """
    Simple health check endpoint to verify backend status.
    """
    return {"status": "ok"}

# Register router
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
