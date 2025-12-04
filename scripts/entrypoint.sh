#!/usr/bin/env bash
set -euo pipefail

DB_URL="${DATABASE_URI:-}"
if [ -z "${DB_URL}" ]; then
  echo "DATABASE_URI is not set; cannot run migrations."
  exit 1
fi

echo "Waiting for database to be reachable at ${DB_URL} ..."
for i in {1..30}; do
  if uv run python - <<PY
import sys
from sqlalchemy import create_engine
engine = create_engine("${DB_URL}")
with engine.connect() as conn:
    conn.execute("SELECT 1")
PY
  then
    echo "Database is up."
    break
  fi
  echo "Database not ready yet, retrying (${i}/30)..."
  sleep 2
done

echo "Running database migrations..."
uv run alembic upgrade head

echo "Starting application..."
exec uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
