# Known Issues And Outstanding Work

This page lists current codebase issues, operational gaps, and external dependencies that future maintainers should understand before changing behavior or planning follow-up work.

## Current Code Issues

- Broker and bulk-import observability is weak. The code logs some broker activity and returns per-record errors from bulk import endpoints, but there is no in-repo mechanism to persist broker run logs or bulk-import outcome logs for later audit. Some sample import and update paths still use `print(...)` instead of structured logging, especially in [samples.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/samples.py).

- `POST /api/v1/assemblies/{assembly_id}/qc-reads/report` requires `bpa_package_id` in the request body. If the intended contract is to identify the package in the path instead, the API shape will need to change in [assemblies.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/assemblies.py) and [qc_read.py](/Users/emilylm/Repositories/atol-database-v2/app/schemas/qc_read.py).

- Assembly stage reporting is effectively one-shot per `(assembly_run_id, stage_name)`. A second `POST` for the same stage is rejected, and `PATCH` replaces the full file list rather than appending to it. The current behavior lives in [assembly_service.py](/Users/emilylm/Repositories/atol-database-v2/app/services/assembly_service.py).

- QC-read reporting always creates a new `QcRead`, new files, and a new draft submission row. There is no deduplication, merge, or reconciliation path in `POST /api/v1/assemblies/{assembly_id}/qc-reads/report`, so repeated reporting can accumulate duplicate or overlapping QC-read records. See [assemblies.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/assemblies.py).

- ToLID external-id selection is likely wrong for the intended workflow. The ToLID service currently prefers the primary sample submission accession and only falls back to `sample.biosample_accession`. If the desired identifier is the BioSample or external accession such as `SAMEA...`, this needs changing in [tolid_service.py](/Users/emilylm/Repositories/atol-database-v2/app/services/tolid_service.py).

- Project parent/child relationships are not represented in the current schema or broker contract. There is no project hierarchy model, join table, or broker payload support for those relationships in [project.py](/Users/emilylm/Repositories/atol-database-v2/app/models/project.py) or [broker.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/broker.py). If ENA requires that structure, Canopy cannot currently enforce it.

- API authorization policy coverage is incomplete. Many endpoints require authentication but do not have an explicit `@policy(...)` decorator. This is especially noticeable across read endpoints in [assemblies.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/assemblies.py), [qc_reads.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/qc_reads.py), [reads.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/reads.py), [projects.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/projects.py), [organisms.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/organisms.py), and others.

- Annotations are not implemented in this codebase. Genome notes do exist as a lightweight CRUD and publish/unpublish feature, but there is no annotation model or annotation API surface. Relevant files are [genome_note.py](/Users/emilylm/Repositories/atol-database-v2/app/models/genome_note.py) and [genome_notes.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/genome_notes.py).

- Project titles are not validated against any ENA-specific minimum length in Canopy. If ENA rejects short titles, that failure will happen downstream rather than being prevented locally. See [project.py](/Users/emilylm/Repositories/atol-database-v2/app/models/project.py) and [project.py](/Users/emilylm/Repositories/atol-database-v2/app/schemas/project.py).

- `scripts/create_user.py` is not portable because it contains a hard-coded repository path in `sys.path`. That should be removed or made relative. See [create_user.py](/Users/emilylm/Repositories/atol-database-v2/scripts/create_user.py).

## Operational Gaps

- There is no in-repo scheduler or automation for recurring BPA imports. The code exposes bulk-import APIs, but nothing in this repo schedules or triggers them automatically.

- There is no in-repo scheduler or automation for retrying `pending` ToLID requests. The code exposes `/broker/tolids/pending` and report endpoints, but retry timing is left to an external broker process.

- Experiment `bioplatforms_base_url` backfill remains a data remediation task. The field exists and is used by assembly helper logic, but the repo cannot tell us which rows in a live database are missing it.

- Manual ToLID backfill is possible through existing endpoints or sample updates, but the repo cannot tell us which real datasets still need patching.

- Backup and snapshot procedures are not documented in the repository. Regular dumps and environment refreshes may be advisable, but the implementation details sit outside this codebase.

## Open Questions And External Dependencies

- Whether the `qc-reads/report` request shape matches genome launcher cannot be confirmed from this repo alone.

- How ENA expects parent and child project relationships to be represented still needs external confirmation.

- Current hosted log-retention settings cannot be determined from the application code.

- The actual user and role setup in dev or prod databases cannot be inferred from the repo, only the supported role names in [policy.py](/Users/emilylm/Repositories/atol-database-v2/app/core/policy.py).

- Whether dev should be regularly refreshed from prod snapshots is an environment-management decision, not something the codebase answers.

## No Longer An Active Code Issue

- Duplicate `assembly_run` registration is already handled. Creating the same `(assembly_id, github_repo, git_commit)` combination returns `409` through [assemblies.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/assemblies.py) and [assembly_service.py](/Users/emilylm/Repositories/atol-database-v2/app/services/assembly_service.py). If failures still occur here, they are a different case than duplicate registration.
