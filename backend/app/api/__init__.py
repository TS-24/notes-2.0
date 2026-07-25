from fastapi import APIRouter

from . import notes, users, word_definitions

api_router = APIRouter(prefix="/api")
api_router.include_router(users.router)
api_router.include_router(notes.router)
api_router.include_router(word_definitions.router)

__all__ = ["api_router"]
