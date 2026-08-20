import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env"))

# No fallback on purpose: this used to default to a URL with a real password
# baked in, which put that credential in a public repo. Fail loudly instead.
SQLALCHEMY_DATABASE_URL = os.environ["DATABASE_URL"]

# Neon suspends idle compute, which kills pooled connections without telling
# the pool. Without pre_ping the first request after a suspend is handed a dead
# connection and fails; recycle keeps one from going stale in the first place.
# Both are no-ops against the SQLite the tests and the desktop build use.
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
