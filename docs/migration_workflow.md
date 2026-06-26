# Migration Workflow

This document describes the migration workflow that is directly evidenced in the current repository.

## Verified

### Migration framework

- Alembic is configured in `alembic/env.py`.
- Active revisions are under `alembic/versions/`.
- Container startup runs `uv run alembic upgrade head` before serving the API (`scripts/entrypoint.sh`).

### Current revision chain

The current active revision sequence in `alembic/versions/` is:

1. `0001_initial_schema`
2. `0002_update_taxon_cols`
3. `0003_assembly_run_github`
4. `0004_qc_reads_assembly_refs`
5. `0005_add_tolid_requests`

### Local developer workflow

1. Ensure the app can resolve `DATABASE_URI`.
2. Apply migrations:

```bash
uv run alembic upgrade head
```

3. Run the test suite:

```bash
pytest -q
```

### Container workflow

- `docker-compose.yml` starts the API container.
- The API container entrypoint waits for the database and then runs:

```bash
uv run alembic upgrade head
```

- If `APP_MODE=migrate`, the entrypoint exits after migrations instead of starting the API.

### Schema snapshot maintenance

The comment at the top of `schema.sql` states that the file should be kept in sync with the database after migrations and regenerated using a schema-only `pg_dump`.

The verified instruction in `schema.sql` is:

```bash
docker compose exec db pg_dump -U <user> -d <dbname> --schema-only --no-owner --no-acl
```

### What recent migrations changed

| Revision | Verified focus |
| --- | --- |
| `0002_update_taxon_cols` | Removes outdated taxonomy columns and adds `assembly.hic_specimen_sample_ids` |
| `0003_assembly_run_github` | Reworks assembly reporting around `assembly_run` and `assembly_stage_run` |
| `0004_qc_reads_assembly_refs` | Reworks QC-read reporting and adds the `qc_read_assembly` link table |
| `0005_add_tolid_requests` | Adds durable ToLID request state |

## Recommended maintainer practice

### For repo changes that include schema updates

1. Add or update the Alembic revision under `alembic/versions/`.
2. Apply the migration to a local database.
3. Update `schema.sql` so it matches the post-migration schema snapshot.
4. Run tests.
5. Update maintainer-facing docs if the schema change affects workflows or operations.

## Unknown From This Repo

- There is no verified production rollback runbook in this repository.
- There is no verified repository-local command for creating new Alembic revisions documented here; the repo only proves how revisions are applied, not the team’s preferred authoring command.
