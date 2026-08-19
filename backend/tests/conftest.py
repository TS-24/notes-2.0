"""
Shared fixtures for the API tests.

The suite runs against in-memory SQLite rather than the compose Postgres. That
is partly convenience — no container to start — and partly the point: the
desktop build ships SQLite, so every test run is also a check that the models
and queries stay portable across both.

`app.db.database` and `app.core.config` read their environment at import time
and deliberately have no fallbacks, so those variables have to exist before
anything under `app` is imported.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
# app.core.config reads this at import time for the same reason, so it has to
# be set here rather than in a fixture: the imports below would already have
# failed by the time any fixture ran.
os.environ.setdefault("JWT_SECRET", "test-secret-never-used-outside-the-suite")

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api import api_router  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.database import get_db  # noqa: E402
from app.db.models import Base, User  # noqa: E402


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


def make_user(db: Session, email: str = "reader@example.com", password: str = "correct horse battery") -> User:
    """An account that can actually be logged into, unlike the old dev user."""
    user = User(
        username=email.split("@")[0],
        email=email,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user(db: Session) -> User:
    return make_user(db)


@pytest.fixture
def other_user(db: Session) -> User:
    """A second account. Nothing can be said about isolation with only one."""
    return make_user(db, email="someone.else@example.com")


@pytest.fixture
def anon_client(db: Session) -> TestClient:
    """A client carrying no credentials, for the refusals."""
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def client(anon_client: TestClient, user: User) -> TestClient:
    """
    The default client, signed in as `user`.

    Authenticated by default because that is the ordinary case: nearly every
    route requires a user, so a suite where the common fixture is anonymous
    would spend most of its lines saying so. The refusals use `anon_client`.
    """
    anon_client.headers["Authorization"] = f"Bearer {create_access_token(user.id)}"
    return anon_client


@pytest.fixture
def other_client(anon_client: TestClient, other_user: User) -> TestClient:
    """A client signed in as `other_user`, for the cross-account tests."""
    client = TestClient(anon_client.app)
    client.headers["Authorization"] = f"Bearer {create_access_token(other_user.id)}"
    return client
