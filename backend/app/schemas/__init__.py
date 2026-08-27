from .auth import LoginRequest, RegisterRequest, TokenResponse
from .note import NoteCreate, NoteRead, NoteUpdate
from .user import UserRead, UserUpdate
from .word_definition import (
    WordDefinitionCreate,
    WordDefinitionRead,
    WordDefinitionUpdate,
)

__all__ = [
    "LoginRequest",
    "NoteCreate",
    "NoteRead",
    "NoteUpdate",
    "RegisterRequest",
    "TokenResponse",
    "UserRead",
    "UserUpdate",
    "WordDefinitionCreate",
    "WordDefinitionRead",
    "WordDefinitionUpdate",
]
