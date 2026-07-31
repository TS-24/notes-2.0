#!/bin/sh
# Bring the schema up to date before serving. Alembic skips revisions that have
# already been applied, so this is safe to run on every container start.
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting API..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
