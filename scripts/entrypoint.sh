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
from sqlalchemy import create_engine, text
engine = create_engine("${DB_URL}")
with engine.connect() as conn:
    conn.execute(text("SELECT 1"))
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

if [ "${ENVIRONMENT:-prod}" = "dev" ]; then
  echo "Starting application (dev mode with reload)..."
  exec uv run --frozen uvicorn app.main:app \
    --host 0.0.0.0 --port "${PORT:-8000}" \
    --reload --reload-dir /app/app
else
  echo "Starting application (production mode)..."
  exec uv run --frozen uvicorn app.main:app \
    --host 0.0.0.0 --port "${PORT:-8000}"
fi
