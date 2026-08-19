from fastapi import APIRouter

from . import analyze, auth, known_words, notes, users, vocab, word_definitions

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(notes.router)
# Before word_definitions: both are mounted at /words, and that router's
# GET /{word_id} takes an int, so a POST to "known" is answered with a 405 by
# the id route before ever reaching the one that handles it.
api_router.include_router(known_words.router)
api_router.include_router(word_definitions.router)
api_router.include_router(vocab.router)
api_router.include_router(analyze.router)

__all__ = ["api_router"]
