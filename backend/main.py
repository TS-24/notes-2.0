import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router

ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
IS_DEVELOPMENT = ENVIRONMENT == "development"

app = FastAPI(
    title="Restyle API",
    description="Backend API for the Restyle application",
    version="1.0.0",
    # The interactive docs are a map of every route, including the auth ones,
    # served to anyone who finds the host. Useful while building, an invitation
    # once this is reachable from outside. Off unless ENVIRONMENT says dev.
    docs_url="/docs" if IS_DEVELOPMENT else None,
    redoc_url="/redoc" if IS_DEVELOPMENT else None,
    openapi_url="/openapi.json" if IS_DEVELOPMENT else None,
)

# In the ordinary path nothing cross-origin reaches this API at all: the
# browser talks to the React Router server, which calls us from its own
# process. This is here for direct callers — /docs, curl, a future client —
# and is a named origin rather than "*" because that wildcard was paired with
# allow_credentials, a combination browsers reject outright for any request
# carrying a cookie. It looked fine only because nothing sent one yet.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:3700")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Simple status check to confirm the backend is reachable."""
    return {"status": "ok"}
