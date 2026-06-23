# Broker And Submission Flows

## Verified

### Active broker API surfaces

The repo currently exposes two broker surfaces in the same router:

#### Flat contract endpoints

- `POST /api/v1/broker/claims/ready`
- `POST /api/v1/broker/claims/entity`
- `POST /api/v1/broker/claims/batch`
- `POST /api/v1/broker/validation`
- `POST /api/v1/broker/reports/{attempt_id}`

These use `Broker*` request/response schemas from `app/schemas/broker_contract.py`.

#### Legacy claim/report endpoints that are still routed

- `POST /api/v1/broker/claim`
- `POST /api/v1/broker/organisms/{taxon_id}/claim`
- `POST /api/v1/broker/attempts/{attempt_id}/lease/renew`
- `POST /api/v1/broker/attempts/{attempt_id}/finalise`
- `POST /api/v1/broker/attempts/{attempt_id}/report`
- `GET /api/v1/broker/attempts`
- `GET /api/v1/broker/attempts/{attempt_id}`
- `GET /api/v1/broker/attempts/{attempt_id}/items`
- `GET /api/v1/broker/organisms/{taxon_id}/summary`

### Submission states and attempt leasing

- `SubmissionAttempt` rows track claim attempts and lease expiry (`app/models/broker.py`).
- The flat contract can claim submissions in either `draft` or `ready` because `CLAIMABLE_SUBMISSION_STATES = ("draft", "ready")` in `app/api/v1/endpoints/broker.py`.
- The legacy claim endpoints only select `draft` rows in their query bodies.
- Claimed rows move to `submitting`, receive `attempt_id`, `lock_acquired_at`, and `lock_expires_at`, and emit `submission_event` rows with `action="claimed"`.
- Lease renewal extends the attempt lease and propagates the new expiry to still-`submitting` rows.
- Finalising an attempt releases remaining `submitting` rows back to `draft` and marks the attempt `complete`.
- Expiring stale leases resets expired `submitting` rows back to `draft` and marks expired attempts as `expired`.

### Broker report behavior

- `POST /api/v1/broker/reports/{attempt_id}` updates claim items using the flat contract.
- `_map_report_state_to_submission_status()` maps:
  - `completed`, `accepted`, `success` -> `accepted`
  - `failed`, `rejected`, `error` -> `rejected`
  - `submitting`, `processing` -> `submitting`
- Accepted reports write `accession` to the submission row and attempt to insert into `accession_registry`.
- Sample reports can also store `secondary_accession` into `biosample_accession`.
- Rejected reports create a new draft submission row for the same entity so the entity becomes claimable again.
- A database integrity conflict during accession registration is translated into HTTP `409` with a message pointing maintainers to `accession_registry`.

### Submission prerequisites and validation

- The broker flat contract resolves existing prerequisite accessions from `accession_registry`, not only from payload fields (`_extract_broker_prerequisites()` in `app/api/v1/endpoints/broker.py`).
- Validation rules currently enforced by `POST /api/v1/broker/validation` are:
  - sample: payload must exist
  - experiment: payload, `sample_accession`, and `project_accession` must exist
  - run: payload, `experiment_accession`, and run file metadata must exist
- Project claims do not include prerequisites.

### ToLID flow

- The ToLID flow does not use broker lease semantics.
- `GET /api/v1/broker/tolids/by-specimen-accession/{specimen_id}` resolves a specimen sample from an accepted sample accession and returns either:
  - stored `tolid_request` state
  - virtual `not_requested` state if no row exists yet
- `POST /api/v1/broker/tolids/{sample_id}/report` lazily creates a `tolid_request` row when needed.
- Allowed reported statuses are `pending`, `assigned`, and `failed`; `not_requested` is rejected by schema validation (`app/schemas/tolid.py`).
- Reporting `assigned` also mirrors the ToLID value onto `sample.tolid`.

### Submission lifecycle rules outside broker.py

- Organism creation creates draft `project_submission` rows immediately.
- Sample creation creates one draft `sample_submission`.
- Experiment creation creates one draft `experiment_submission`.
- Assembly QC reporting creates one draft `qc_read_submission`.
- Sample and experiment edits can create replacement draft submission rows as described in `system_overview.md`.

## Inferences

- The flat broker contract appears to be the newer interface and the legacy claim/report endpoints appear to be retained for compatibility, because both sets are active and the newer set uses dedicated broker-contract schemas.

## Unknown From This Repo

- Which broker surface is used by current production callers.
- Who or what changes submission rows from `draft` to `ready`.
- Whether `ready` means human-reviewed, machine-validated, or both.
