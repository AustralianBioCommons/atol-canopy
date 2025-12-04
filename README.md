# Canopy: A Metadata Tracking System for the Australian Tree of Life (AToL) data

Canopy is a FastAPI backend used to track and manage genomic data for the Australian Tree of Life (AToL) project.

## Overview

Canopy manages metadata across core biological entities (Organism, Sample, Experiment, Read, Assembly, Project, BPA Initiative, Genome Note), and models each submission lifecycle with a two-table pattern per entity:
- Main: current state
- Submission: staged for external submission (e.g., ENA)

A dedicated broker workflow enables integration with external submission pipelines. The broker can claim work (with short leases) and report outcomes/accessions back to Canopy. Helper endpoints provide attempt summaries and item listings to power a simple dashboard or external UI.

## Features

- Authentication & tokens: JWT access, refresh, and logout endpoints
- Role-based access control: user, curator, broker, genome_launcher, admin, superuser
- RESTful APIs for core entities (organisms, samples, experiments, reads, assemblies, projects, genome notes, BPA initiatives)
- Submission workflow endpoints (sample-submissions, experiment-submissions, read-submissions)
- Broker endpoints to support external submission pipelines:
  - Claim drafts and obtain a lease: `/api/v1/broker/organisms/{organism_key}/claim`
  - Renew lease, finalise, and report results: `/api/v1/broker/attempts/{attempt_id}/...`
  - Attempt listing and summaries for dashboard views
- Bulk import endpoints for organisms, samples, and experiments
- XML export endpoints for downstream systems
- PostgreSQL database with UUID primary keys and JSONB fields; schema bootstrapped via Docker using `schema.sql`
- Docker Compose for local development, plus an alternative local (non-Docker) run mode

## Tech Stack

- Python 3.10, FastAPI, Uvicorn
- SQLAlchemy 2.x ORM
- Pydantic v2 + pydantic-settings
- PostgreSQL 14
- JWT auth via python-jose[cryptography]; password hashing via passlib[bcrypt]
- Alembic (available); schema initialization via `schema.sql` in Docker
- Docker & Docker Compose

## Project Structure

```
app/
├── main.py
├── api/
│   └── v1/
│       ├── api.py
│       └── endpoints/
│           ├── auth.py
│           ├── users.py
│           ├── organisms.py
│           ├── samples.py
│           ├── sample_submissions.py
│           ├── experiments.py
│           ├── experiment_submissions.py
│           ├── reads.py
│           ├── read_submissions.py
│           ├── assemblies.py
│           ├── projects.py
│           ├── bpa_initiatives.py
│           ├── genome_notes.py
│           ├── broker.py
│           └── xml_export.py
├── core/
│   ├── dependencies.py
│   ├── security.py
│   └── settings.py
├── db/
│   └── session.py
├── models/
│   ├── user.py, token.py
│   ├── organism.py, sample.py, experiment.py, read.py
│   ├── assembly.py, project.py, bpa_initiative.py, genome_note.py
│   ├── accession_registry.py, broker.py
│   └── (SQLAlchemy models)
└── schemas/
    ├── user.py
    ├── organism.py, sample.py, experiment.py, read.py
    ├── assembly.py, project.py, bpa_initiative.py, genome_note.py
    └── (Pydantic schemas)

# Top-level
pyproject.toml, uv.lock, docker-compose.yml, Dockerfile, schema.sql, scripts/, docs/, data/
```

## Getting Started

  ### Prerequisites

  - Docker and Docker Compose
  - [uv](https://docs.astral.sh/uv/) for local (non-Docker) development

  ### Running the Application (Docker)

  1) Create your environment file from the template:

  ```bash
  cp .env.example .env
  ```

  2) Edit `.env` and set the required values. At minimum:
  - `POSTGRES_USER=postgres`
  - `POSTGRES_PASSWORD=<enter password>`
  - `POSTGRES_DB=atol_db`
  - `POSTGRES_PORT=5432`  # container port (host is mapped to 5433)
  - `POSTGRES_SERVER=db`  # do not change; this is the Docker service name
  - `JWT_SECRET_KEY=<enter random hex string>`
  - `JWT_ALGORITHM=HS256`

  Generate a secure secret (macOS/Linux):

  ```bash
  openssl rand -hex 32
  ```

  3) Build and start the stack:

  ```bash
  docker compose up -d --build    # Compose v2
  # or
  docker-compose up -d --build    # older Compose
  ```

  4) Tail logs (optional) and wait for the API to be ready:

  ```bash
  docker compose logs -f api
  ```

  5) Open the API docs:

  - Swagger UI: http://localhost:8000/api/v1/docs
  - ReDoc: http://localhost:8000/api/v1/redoc

  6) Stop the stack:

  ```bash
  docker compose down
  ```

  To reset the database (this will delete your data):

  ```bash
  docker compose down -v
  ```

  Note on code changes (Docker): the API container runs uvicorn without `--reload`. If you edit code, restart the API container to pick up changes:

  ```bash
  docker compose restart api
  ```

  #### Local database access (via Docker)
  Connect to the Postgres database hosted on the `db` container using `psql`.

  - Quick one-liner (uses credentials created by `.env` during container init):

    ```bash
    docker compose exec db psql -U postgres -d atol_db
    ```

  - Or open a shell in the container first, then run psql:

    ```bash
    docker compose exec -it db bash
    psql -U postgres -d atol_db
    ```

  Once in psql, you can run SQL and handy meta-commands:

  ```sql
  -- List databases
  \l
  -- Connect to a database (if needed)
  \c atol_db
  -- List schemas
  \dn
  -- List tables (optionally by schema)
  \dt
  \dt public.*
  -- Describe a table
  \d+ public.users
  -- Run a query
  SELECT NOW();
  -- Quit psql
  \q
  ```

  ### Create your first user
  On a fresh database you will likely want to create an initial user (e.g. an admin/broker) so you can log in and use secured endpoints. Use the helper script from the project root on your host machine:

  ```bash
  python scripts/create_user.py \
    --host localhost \
    --port 5433 \
    --dbname atol_db \
    --user postgres \
    --password <db_password_from_.env> \
    --username admin \
    --email admin@example.org \
    --user-password <choose_app_password> \
    --role user
  ```

  You will need to manually update the role for your first user in the database.

  Then obtain a JWT to call secured endpoints:

  ```bash
  # Exchange username/password for tokens
  curl -s -X POST http://localhost:8000/api/v1/auth/login \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d 'username=admin&password=<choose_app_password>'
  ```

  Export the returned `access_token` and use it in the `Authorization: Bearer <token>` header.

  ### Broker integration quickstart
  The broker API provides claim/report endpoints to integrate with an external submission pipeline.

  - Claim items for an organism (example):

    ```bash
    TOKEN=<your_access_token>
    curl -s -X POST "http://localhost:8000/api/v1/broker/organisms/<organism_key>/claim?per_type_limit=100" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"lease_duration_minutes": 30}'
    ```

  - Report results for an attempt (example shape):

    ```bash
    curl -s -X POST "http://localhost:8000/api/v1/broker/attempts/<attempt_id>/report" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"samples": [], "experiments": [], "reads": [], "projects": []}'
    ```

  For a deeper overview of attempt leasing and statuses, see the `broker` endpoints in `app/api/v1/endpoints/broker.py` and the interactive docs.

  ## Bulk Import API

The system provides API endpoints for bulk importing organisms, samples, and experiments. These endpoints allow you to import data in the same format as the standalone import script but through authenticated API calls.

### Bulk Import Endpoints

- `/api/v1/organisms/bulk-import` - Bulk import organisms
- `/api/v1/samples/bulk-import` - Bulk import samples
- `/api/v1/experiments/bulk-import` - Bulk import experiments

All bulk import endpoints:
- Require authentication with 'curator' or 'admin' role
- Accept JSON data in the same format as the standalone import script
- Return counts of created and skipped records

### Example usage

See `docs/bulk_import_api.md` for request formats and curl examples for organisms, samples, and experiments.

4. Access the API documentation at http://localhost:8000/api/v1/docs

### Authentication

The API uses JWT tokens for authentication. To authenticate:

1. Create a user or use a default admin user
2. Get a token from `/auth/login` endpoint
3. Use the token in the Authorization header: `Bearer {token}`

## API Documentation

Once the application is running, you can access the interactive API documentation:

- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc

## Role-Based Access Control

The system implements role-based access control with the following roles:

- **user**: Basic read access to data
- **curator**: Can create and update biological entities
- **broker**: Can claim and report biological entities
- **genome_launcher**: Can access data required by genome assembly & post-assembly pipelines and report results
- **admin**: Full access to all endpoints
- **superuser**: Special role with delete permissions

## Development (run without Docker)

  Prefer Docker for a consistent setup. This section shows how to run the FastAPI app directly on your machine as an alternative.

  1) Sync the environment with uv (creates `.venv` in the project root):

  ```bash
  uv sync --dev
  # Optional: source .venv/bin/activate
  ```

  2) Configure environment

  - Copy `.env.example` to `.env` and fill the required values (particularly `JWT_SECRET_KEY`, `JWT_ALGORITHM`).
  - Choose ONE of the database options below:

  Option A — reuse the Docker Postgres (recommended)

  ```bash
  # Start only the database service
  docker compose up -d db

  # In your .env (or environment), point to the compose database on host 5433
  POSTGRES_SERVER=localhost
  POSTGRES_PORT=5433
  POSTGRES_USER=postgres
  POSTGRES_PASSWORD=<db_password_from_.env>
  POSTGRES_DB=atol_db
  ```

  Option B — use a local Postgres (no Docker)

  ```bash
  # Ensure Postgres is running locally (port 5432)
  # Create the database and apply the schema
  createdb -h localhost -U postgres atol_db || true
  psql -h localhost -U postgres -d atol_db -f schema.sql

  # In your .env (or environment), point to your local instance
  POSTGRES_SERVER=localhost
  POSTGRES_PORT=5432
  POSTGRES_USER=postgres
  POSTGRES_PASSWORD=<your_local_password>
  POSTGRES_DB=atol_db
  ```

  3) Run the application

  ```bash
  uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ```

  4) Open the docs at http://localhost:8000/api/v1/docs

  ### Linting

  - Install hooks: `uv run pre-commit install`
  - Run all checks: `uv run pre-commit run --all-files`
  - Install commit message hook: `uv run pre-commit install --hook-type commit-msg` (requires commitlint hook configured)

  ### Environment configuration

Configuration is provided via environment variables loaded from `.env` (see `.env.example`). Key settings:

- Database
  - `POSTGRES_SERVER` (Docker service name is `db`)
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`
  - `POSTGRES_DB`
  - `POSTGRES_PORT` (container port, default 5432; host is `5433` via compose)
- Auth
  - `JWT_SECRET_KEY` (required)
  - `JWT_ALGORITHM` (e.g. `HS256`)
  - `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 150)
  - `JWT_REFRESH_TOKEN_EXPIRE_DAYS` (default 7)
- CORS
  - `BACKEND_CORS_ORIGINS` (JSON array of origins)

When using Docker, the database is initialized automatically on first run using `schema.sql` via the Postgres container's init hook.

## License

This project is licensed under the GPL-3.0-or-later License.
