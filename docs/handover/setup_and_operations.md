# Local Setup And Operations

## Verified

### Container startup path

- `docker-compose.yml` defines two services:
  - `api` on host port `8000`
  - `db` on host port `5433`, container port `5432`
- The API container runs `scripts/entrypoint.sh` from `Dockerfile`.
- `scripts/entrypoint.sh` does the following:
  1. requires `DATABASE_URI` to be present in the environment
  2. waits for the database to answer `SELECT 1`
  3. runs `uv run alembic upgrade head`
  4. starts `uvicorn`
  5. enables `--reload` only when `ENVIRONMENT=dev`

### Local Docker workflow

1. Copy `.env.example` to `.env`.
2. Set at least the JWT variables and Postgres variables needed by the app.
3. Start the stack with `docker compose up --build`.
4. API docs are served from `/api/v1/docs`, `/api/v1/redoc`, and `/api/v1/openapi.json`.

### Non-Docker workflow

The repo contains enough evidence for this local path:

1. Install dependencies with `uv sync --dev --frozen` (`Dockerfile`, `.github/workflows/lint.yml`).
2. Export the required environment variables described in `app/core/settings.py`.
3. Run migrations with `uv run alembic upgrade head`.
4. Start the API with `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.

### First-user creation

- `scripts/create_user.py` creates a user directly in the database and hashes the password with the same helper used by the API.
- The script accepts either `--db-uri` or host/port/name/user/password fields.
- The script sets `roles=[role]`.
- The script sets `is_superuser=True` only when `--role superuser`.

### Recurring maintainer tasks visible in the repo

| Task | Verified implementation |
| --- | --- |
| Run tests | `pytest -q` passes in the current repo state |
| Apply schema changes | `uv run alembic upgrade head` |
| Expire stale broker leases from code | `scripts/expire_leases.py` |
| Expire stale broker leases via API | `POST /api/v1/admin/leases/expire` or `POST /api/v1/broker/leases/expire` |
| Check liveness | `GET /health` |
| Check app version | `GET /version` |
| Regenerate schema snapshot | Comment in `schema.sql` says to use `pg_dump --schema-only` after migrations |

### Deployment automation evidenced in the repo

- `.github/workflows/build-and-deploy-dev.yml` builds a container image, pushes it to ECR, and invokes a Lambda deployment function.
- `.github/workflows/build-publish.yml` builds and pushes release-tagged images to ECR.
- These workflows prove that the repo is wired to AWS-hosted automation, but they do not describe the runtime environment behind the deployment target.

### Operational sharp edges visible in code

- `scripts/entrypoint.sh` requires a literal `DATABASE_URI` shell variable even though `app/core/settings.py` can derive `DATABASE_URI` from `POSTGRES_*` values. This means `POSTGRES_*` values alone are enough for direct Python startup but not enough for the entrypoint script.
- `scripts/create_user.py` appends a hard-coded repository path to `sys.path`. That makes the script repo-location-sensitive.
- There are two lease-expiry implementations:
  - `app/services/broker_service.py`
  - `expire_stale_leases()` inside `app/api/v1/endpoints/broker.py`

## Inferences

- `schema.sql` is a maintained schema snapshot rather than the runtime bootstrap path, because container startup applies Alembic migrations and does not execute `schema.sql` directly.

## Unknown From This Repo

- The exact production release checklist after a successful GitHub Actions deployment.
- Whether there are environment-specific manual steps around database backups, smoke tests, or rollback outside the repository.
