# Troubleshooting Guide

## Verified

| Symptom | Likely component | Files, endpoints, or scripts to inspect | Verified next checks |
| --- | --- | --- | --- |
| API container exits before serving requests | Startup config or DB connectivity | `scripts/entrypoint.sh`, `docker-compose.yml`, `app/core/settings.py` | Confirm `DATABASE_URI` is set in the shell environment seen by the entrypoint, not just derivable from `POSTGRES_*`; confirm DB answers `SELECT 1`; confirm Alembic can reach the same URI |
| App import fails with a settings error | Missing JWT or DB settings | `app/core/settings.py` | Check `JWT_SECRET_KEY`, `JWT_ALGORITHM`, and either `DATABASE_URI` or all `POSTGRES_*`; in `prod`, confirm `BACKEND_CORS_ORIGINS` is not `["*"]` |
| Login works but refresh fails with `401 Invalid or expired refresh token` | Refresh-token lookup or revocation | `app/api/v1/endpoints/auth.py`, `app/models/token.py` | Check whether the token hash exists in `refresh_token`, whether `expires_at` is still in the future, and whether `revoked` is already true |
| Sample or experiment update is rejected while broker work is in progress | Submission lock state | `app/api/v1/endpoints/samples.py`, `app/services/experiment_service.py`, broker attempt routes | Check the latest submission row status; both code paths block edits when the latest submission is `submitting` |
| Broker cannot claim work that maintainers expect to be available | Submission status, claim surface, or stale lease | `app/api/v1/endpoints/broker.py`, `scripts/expire_leases.py`, `POST /api/v1/admin/leases/expire`, `POST /api/v1/broker/leases/expire` | Check whether rows are still `draft` versus `ready`; flat broker claims accept `draft` and `ready`, legacy organism claim accepts only `draft`; check `lock_expires_at`; expire stale leases if needed |
| Broker report returns `409` mentioning integrity constraints | Accession registry conflict | `app/api/v1/endpoints/broker.py`, `app/models/accession_registry.py` | Inspect `accession_registry` for an existing row with the same accession bound to a different entity; inspect the affected submission row’s accession FK fields |
| ToLID lookup by accession returns `404` | Sample accession resolution or sample kind | `app/services/tolid_service.py`, `app/models/tolid_request.py`, `GET /api/v1/broker/tolids/...` | Confirm there is an accepted `sample_submission.accession` or `sample.biosample_accession`; confirm the resolved sample has `kind = specimen` |
| ToLID report cannot create a row | Missing accepted sample accession | `app/services/tolid_service.py` | Check whether `_fallback_external_id()` can find a sample submission accession or `sample.biosample_accession`; without one, reporting returns `tolid_external_id_missing` |
| Assembly intent returns `422` for specimen samples | Sample lineage or experiment-platform validation | `app/api/v1/endpoints/assemblies.py`, `app/services/assembly_helper.py` | Confirm each supplied sample exists, is `kind='specimen'`, and matches the route `taxon_id`; confirm long-read experiments exist with platform `PACBIO_SMRT` or `OXFORD_NANOPORE`; confirm Hi-C experiments are `ILLUMINA` plus library strategy `HI-C` |
| Assembly QC read reporting returns `422` | Manifest mismatch or lineage mismatch | `POST /api/v1/assemblies/{assembly_id}/qc-reads/report`, `app/api/v1/endpoints/assemblies.py` | Confirm `bpa_package_id` resolves to an experiment; confirm the experiment sample belongs to the assembly’s allowed specimen lineage; confirm the package ID exists in `assembly.manifest_json["read_files"]`; confirm the supplied source MD5 values match `read.file_checksum` rows for that experiment |
| Genome note publish returns `409` | Existing published note for the same organism | `app/services/genome_note_service.py`, `app/api/v1/endpoints/genome_notes.py` | Check whether another `genome_note` row for the same `taxon_id` already has `is_published = true` |
| Taxonomy bulk import skips rows unexpectedly | Missing organism rows or unmapped NCBI enrichment | `app/services/taxonomy_info_service.py`, `app/services/ncbi_taxonomy_service.py` | Check whether each `taxon_id` already exists in `organism`; inspect `errors`, `ncbi_retryable_count`, and `ncbi_retryable_taxon_ids` in the bulk response |
| User-creation script fails in an unexpected checkout location | Hard-coded import path in script | `scripts/create_user.py` | Check the `sys.path.append("/Users/emilylm/Repositories/atol-database-v2")` line and adjust it if the repo is moved |

## Verified Sharp Edges And Technical Debt

- There are two different lease-expiry implementations with overlapping responsibilities.
- Broker APIs are duplicated across legacy and newer contract routes.
- Submission status `ready` is part of the API contract, but this repo does not show who sets it.
- Several code comments and docstrings are stale. One example is the PacBio filtering note in `app/services/assembly_helper.py`, while tests in `tests/unit/services/test_assembly_helper.py` assert that all PacBio reads are currently included when they have `file_name`.
- The sample endpoint contains several `print(...)` debugging paths instead of structured logging.
