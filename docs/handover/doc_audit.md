# Documentation Audit

## Verified

| Document or file | Status | Evidence | Action needed |
| --- | --- | --- | --- |
| `README.md` | stale | References `xml_export.py` and `read_submissions.py`, but those routes are not registered in `app/api/v1/api.py`; says Docker uses `schema.sql` bootstrap and no reload, while `scripts/entrypoint.sh` runs `alembic upgrade head` and starts `uvicorn --reload` when `ENVIRONMENT=dev` | Keep only as a verified pointer to the handover pack |
| `docs/assembly_reporting_api.md` | verified current | Matches active assembly intent, run, QC-report, and stage-run endpoints in `app/api/v1/endpoints/assemblies.py`; supported by `tests/unit/endpoints/test_endpoints_assemblies.py` and `tests/unit/services/test_assembly_helper.py` | Keep; continue treating as the current assembly-specific API doc |
| `docs/auth_refresh_tokens.md` | verified current | Rewritten from `app/api/v1/endpoints/auth.py`, `app/core/security.py`, `app/core/dependencies.py`, `app/models/token.py`, and auth endpoint tests | Keep |
| `docs/broker_prerequisites_enhancement.md` | partially current | Accession lookup behavior matches `_extract_broker_prerequisites()` in `app/api/v1/endpoints/broker.py`; document discusses `validation_hints` and `file_metadata`, but current response schema exposes `files`, and code does not populate `file_metadata` | Do not use as operator guidance without rewriting |
| `docs/bulk_import_api.md` | verified current | Rewritten from current organism, sample, experiment, and taxonomy bulk-import code paths | Keep |
| `docs/migration_workflow.md` | verified current | Rewritten to cover only Alembic, `schema.sql`, Docker entrypoint behavior, and active revision files evidenced in the repo | Keep |
| `docs/ncbi_taxonomy_sync.md` | verified current | Matches canonical scientific-name recomputation in `app/services/organism_service.py` and NCBI enrichment behavior in `app/services/taxonomy_info_service.py`; backed by `tests/unit/services/test_taxonomy_info_service.py` | Keep |
| `docs/tolid_broker_api.md` | verified current | Matches `app/services/tolid_service.py`, `app/schemas/tolid.py`, and ToLID routes in `app/api/v1/endpoints/broker.py`; backed by `tests/unit/endpoints/test_endpoints_broker_tolids.py` | Keep |
| `docs/xml_export_api.md` | stale | No `xml-export` router is included in `app/api/v1/api.py`, and there is no active `app/api/v1/endpoints/xml_export.py` file | Removed from the repo during handover cleanup |
| `postman/Canopy.postman_collection.json` | stale | Contains outdated paths and examples such as organism lookup by grouping key; includes embedded example credentials/tokens; current router surface is different in `app/api/v1/api.py` | Regenerate a minimal core collection from the current API surface |
| `data/docs/MIGRATION_MERGE_INSTRUCTIONS.md` | stale | Refers to migration chain ending at `0009...` and files that are no longer current; active Alembic head is `0005_add_tolid_requests.py` under the current chain | Treat as historical notes only |
| `data/docs/MIGRATION_NOTES.md` | stale | Refers to `0010_rename_base_url_to_bioplatforms_base_url.py`, which is not in the active migration chain | Treat as historical notes only |
| `data/docs/PR_QC_READ_SUBMISSION.md` | stale | Mentions `POST /qc-callbacks` and inactive `read_submissions.py`; current QC reporting route is `POST /api/v1/assemblies/{assembly_id}/qc-reads/report` | Treat as historical PR commentary only |
| `data/docs/SCHEMA_COMPARISON_REPORT.md` | stale | Describes schema mismatches relative to an older `schema3.sql` dump that is not present as current source of truth | Treat as historical notes only |
| `data/docs/SCHEMA_UPDATE_SUMMARY.md` | stale | Refers to removed `read_submission` decisions and older QC-read schema shape; current schema and migrations have moved on | Treat as historical notes only |
| `data/docs/SCHEMA_VERIFICATION.md` | stale | Claims a structural state from 2026-04-30 that predates current assembly and ToLID migrations | Treat as historical notes only |
| `docs/handover/*.md` | missing before this update | No maintainer-oriented handover pack existed in the repo | Created in this update |

## Inferences

- The `data/docs/` files appear to be temporary change notes rather than maintained operator documentation, because they describe one-off migration merges, PR summaries, and schema comparisons rather than current runtime behavior.

## Unknown From This Repo

- Whether the stale docs should be deleted, archived elsewhere, or retained for audit history.
