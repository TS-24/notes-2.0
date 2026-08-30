from fastapi import APIRouter

from . import (
    auth,
    chats,
    invites,
    notes,
    password_resets,
    settings,
    users,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(settings.router)
api_router.include_router(invites.router)
api_router.include_router(password_resets.router)
api_router.include_router(notes.router)
api_router.include_router(chats.router)

__all__ = ["api_router"]
