"""
Shared fixtures for the API tests.

The suite runs against in-memory SQLite rather than the compose Postgres. That
is partly convenience — no container to start — and partly the point: the
desktop build ships SQLite, so every test run is also a check that the models
and queries stay portable across both.

`app.db.database` reads DATABASE_URL at import time and deliberately has no
fallback, so the variable has to exist before anything under `app` is imported.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api import api_router  # noqa: E402
from app.db.database import get_db  # noqa: E402
from app.db.models import Base  # noqa: E402


@pytest.fixture
def db() -> Session:
    """
    A session on a fresh in-memory database, one per test.

    StaticPool keeps every connection pointed at the same in-memory database:
    without it SQLite hands out a new empty one per connection, and the tables
    created here would be invisible to the request handler under test.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db: Session) -> TestClient:
    """A client whose requests run against the same session the test holds."""
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)
