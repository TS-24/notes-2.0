from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router

app = FastAPI(
    title="Restyle API",
    description="Backend API for the Restyle application",
    version="1.0.0",
)

# Allow the React Router frontend (served on :3000 by docker compose) to call us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Simple status check to confirm the backend is reachable."""
    return {"status": "ok"}
