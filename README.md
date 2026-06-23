# Canopy Handover Entry Point

This repository contains a FastAPI application for tracking organism, sample, experiment, read, assembly, project, QC-read, genome-note, taxonomy, user, broker-attempt, and ToLID-request metadata for the Australian Tree of Life project.

This `README` has been reduced to verified pointers. The detailed handover pack created from the current codebase is in `docs/handover/`.

## Verified Starting Points

- API app entrypoint: `app/main.py`
- Versioned API router: `app/api/v1/api.py`
- Runtime settings: `app/core/settings.py`
- Database session setup: `app/db/session.py`
- Docker startup path: `Dockerfile`, `docker-compose.yml`, `scripts/entrypoint.sh`
- Schema and migrations: `schema.sql`, `alembic/env.py`, `alembic/versions/`
- Test suite: `tests/`

## Handover Pack

- Overview and structure: `docs/handover/README.md`
- Documentation audit: `docs/handover/doc_audit.md`
- System and lifecycle overview: `docs/handover/system_overview.md`
- Local setup and operations: `docs/handover/setup_and_operations.md`
- Broker and submission flows: `docs/handover/broker_and_submission_flows.md`
- Config and environment reference: `docs/handover/config_reference.md`
- Troubleshooting guide: `docs/handover/troubleshooting.md`
- Open questions and tribal knowledge gaps: `docs/handover/open_questions.md`
