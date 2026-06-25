# Canopy

Canopy is a FastAPI backend for managing metadata and submission-tracking records for the Australian Tree of Life project.

This `README` is the central repository document. It gives the verified high-level picture of the application and links to more detailed maintainer documentation where the detail would otherwise make this file unwieldy.

## Verified Scope

The current codebase stores and serves metadata for:

- organisms
- taxonomy enrichment records
- samples and specimen-to-derived sample lineage
- experiments
- reads
- QC-read results
- assemblies, assembly runs, and assembly stage runs
- projects
- BPA initiatives
- genome notes
- users and refresh tokens
- broker submission attempts, events, and ToLID request state

Primary implementation paths:

- API app: `app/main.py`
- Versioned router: `app/api/v1/api.py`
- Runtime settings: `app/core/settings.py`
- Models: `app/models/`
- Schemas: `app/schemas/`
- Shared business logic: `app/services/`
- Migrations: `alembic/versions/`

## How The System Works

### Core pattern

Several entities use a main-table plus submission-table pattern.

- Main table: current application-facing record
- Submission table: staged payloads and submission lifecycle state for external workflows

This pattern is visible for:

- projects
- samples
- experiments
- QC reads
- assemblies

### Broker-facing workflow

The repo exposes broker endpoints under `/api/v1/broker/...` for claiming work, validating payload prerequisites, reporting outcomes, finalising failed attempts, and managing ToLID request state.

The currently routed claim/report surface is:

- `/broker/claims/ready`
- `/broker/claims/entity`
- `/broker/claims/batch`
- `/broker/validation`
- `/broker/reports/{attempt_id}`
- `/broker/attempts/{attempt_id}/finalise`

Detailed broker lifecycle notes are in [docs/handover/broker_and_submission_flows.md](docs/handover/broker_and_submission_flows.md).

### Assembly workflow

The current assembly flow is centered on:

1. creating an assembly intent
2. generating and storing an assembly manifest
3. registering assembly pipeline runs by GitHub repo and commit
4. reporting QC-read outputs
5. reporting per-stage results

Detailed assembly instructions are in [docs/assembly_reporting_api.md](docs/assembly_reporting_api.md).

## Active Documentation

### Start here for maintainers

- [docs/handover/README.md](docs/handover/README.md)

### Feature and operations docs verified against current code

- [docs/assembly_reporting_api.md](docs/assembly_reporting_api.md)
- [docs/auth_refresh_tokens.md](docs/auth_refresh_tokens.md)
- [docs/bulk_import_api.md](docs/bulk_import_api.md)
- [docs/migration_workflow.md](docs/migration_workflow.md)
- [docs/ncbi_taxonomy_sync.md](docs/ncbi_taxonomy_sync.md)
- [docs/tolid_broker_api.md](docs/tolid_broker_api.md)

### Handover pack contents

- [docs/handover/system_overview.md](docs/handover/system_overview.md)
- [docs/handover/setup_and_operations.md](docs/handover/setup_and_operations.md)
- [docs/handover/broker_and_submission_flows.md](docs/handover/broker_and_submission_flows.md)
- [docs/handover/config_reference.md](docs/handover/config_reference.md)
- [docs/handover/troubleshooting.md](docs/handover/troubleshooting.md)
- [docs/handover/open_questions.md](docs/handover/open_questions.md)

## Local Development

### Requirements

- Docker and Docker Compose for the container-based local path
- or `uv` plus a reachable PostgreSQL instance for the non-Docker local path

### Environment and settings

Settings are defined in `app/core/settings.py`.

At application import time, the code requires:

- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `DATABASE_URI`, or enough `POSTGRES_*` values for `DATABASE_URI` to be derived

At container entrypoint time, `scripts/entrypoint.sh` requires `DATABASE_URI` to exist in the shell environment before it will run migrations.

The repository includes:

- `.env.example`
- `docker-compose.yml`
- `Dockerfile`
- `scripts/entrypoint.sh`

### Docker path

1. Copy the template:

```bash
cp .env.example .env
```

2. Set the required values in `.env`.

3. Start the stack:

```bash
docker compose up --build
```

4. Open the API docs:

- `http://localhost:8000/api/v1/docs`
- `http://localhost:8000/api/v1/redoc`

The Docker Compose file maps:

- API: host `8000` -> container `8000`
- Postgres: host `5433` -> container `5432`

### Non-Docker path

1. Install dependencies:

```bash
uv sync --dev --frozen
```

2. Export the required environment variables.

3. Apply migrations:

```bash
uv run alembic upgrade head
```

4. Start the API:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Database And Migrations

- SQLAlchemy session setup is in `app/db/session.py`.
- Alembic config is in `alembic/env.py`.
- Active revisions are in `alembic/versions/`.
- `scripts/entrypoint.sh` runs `uv run alembic upgrade head` before starting the app.
- `schema.sql` is maintained as a schema snapshot, not the runtime bootstrap mechanism.

For the repo-local migration workflow, see [docs/migration_workflow.md](docs/migration_workflow.md).

## Authentication

The current authentication surface is:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`

Access tokens are JWTs. Refresh tokens are stored as hashed values in the `refresh_token` table.

Detailed auth behavior is in [docs/auth_refresh_tokens.md](docs/auth_refresh_tokens.md).

## Useful Entry Points

### API docs and health

- OpenAPI JSON: `/api/v1/openapi.json`
- Swagger UI: `/api/v1/docs`
- ReDoc: `/api/v1/redoc`
- Health: `/health`
- Version: `/version`

### Scripts

- `scripts/entrypoint.sh`: wait for DB, run migrations, start app
- `scripts/create_user.py`: create a user directly in the database
- `scripts/expire_leases.py`: expire broker leases directly from Python

## Testing

The repository contains unit tests under `tests/`.

Run them with:

```bash
pytest -q
```

## Known Limits Of This Repository

The repository does not by itself tell us:

- which broker API surface is used in production
- who or what promotes submission rows from `draft` to `ready`
- the full production runtime topology behind the GitHub Actions deployment workflows
- any external runbooks or operational conventions outside version control
