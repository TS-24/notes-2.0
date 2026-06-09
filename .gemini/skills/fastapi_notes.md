# FastAPI Notes API Skill

## Purpose
This skill provides instructions and a standard format for creating FastAPI endpoints specifically tailored for handling `Note` objects in the Notes 2.0 application.

## Note Schema Definition
When building APIs or defining Pydantic models for notes, always adhere to the following data structure, which maps directly to the frontend's TypeScript `Note` interface:

```typescript
interface Note {
  id: string;
  title: string;
  content: string;
  colorId: string; // References COLORS key
  isPinned: boolean;
  createdAt?: string;
}
```

### Pydantic Model Representation
When defining this in Python/FastAPI, use the following `BaseModel` from Pydantic:

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Note(BaseModel):
    id: str
    title: str
    content: str
    colorId: str
    isPinned: bool
    createdAt: Optional[datetime] = None
```

## Guidelines for Creating APIs
1. **Routing**: Use an `APIRouter` to group note-related endpoints (e.g., `router = APIRouter(prefix="/notes", tags=["notes"])`).
2. **Payloads**: Always use the `Note` Pydantic model for receiving payloads (POST/PUT) and returning responses to ensure type consistency with the frontend.
3. **Data Operations**: When implementing APIs for creating, reading, updating, or deleting notes, assume the frontend will send data adhering strictly to the schema.
4. **Analysis Integration**: If the API involves analyzing the `content` of the note (e.g., using `nltk` or `textstat`), ensure the analysis logic extracts the text strictly from the `content` field of the Note model.
