# Broker And Submission Flows

## Verified

### Active broker API surfaces

The repo currently exposes these broker submission endpoints:

- `POST /api/v1/broker/claims/ready`
- `POST /api/v1/broker/claims/entity`
- `POST /api/v1/broker/claims/batch`
- `POST /api/v1/broker/validation`
- `POST /api/v1/broker/reports/{attempt_id}`
- `POST /api/v1/broker/attempts/{attempt_id}/finalise`

The claim, validation, and report endpoints above use a shared broker schema from `app/schemas/broker_contract.py`.
Claims return a single `entities` list where each item includes its own `type`, `id`, payload, prerequisites, and file metadata.

### Legacy handler status

- The module still contains older claim/report helper functions such as `claim_by_entity_ids()`, `claim_drafts_for_organism()`, `renew_attempt_lease()`, `report_results()`, `list_attempts()`, `get_attempt()`, `get_attempt_items()`, and `organism_summary()`.
- These are out-dated. I've removed the routes that were exposing these functions, but I've kept the functions for the moment (didn't have time to remove). Remove in future!

### Submission states and attempt leasing

- `SubmissionAttempt` rows track claim attempts and lease expiry (`app/models/broker.py`).
- The current broker claim endpoints can claim submissions in either `draft` or `ready` because `CLAIMABLE_SUBMISSION_STATES = ("draft", "ready")` in `app/api/v1/endpoints/broker.py`.
- Claimed rows move to `submitting`, receive `attempt_id`, `lock_acquired_at`, and `lock_expires_at`, and emit `submission_event` rows with `action="claimed"`.
- Finalising an attempt releases remaining `submitting` rows back to `draft` and marks the attempt `complete`.
- Expiring stale leases resets expired `submitting` rows back to `draft` and marks expired attempts as `expired`.

### Broker report behavior

- `POST /api/v1/broker/reports/{attempt_id}` updates the entities claimed under one broker attempt.
- `_map_report_state_to_submission_status()` maps:
  - `completed`, `accepted`, `success` -> `accepted`
  - `failed`, `rejected`, `error` -> `rejected`
  - `submitting`, `processing` -> `submitting`
- Accepted reports write `accession` to the submission row and attempt to insert into `accession_registry`.
- Sample reports can also store `secondary_accession` into sample.`biosample_accession`.
- Rejected reports create a new draft submission row for the same entity so the entity becomes claimable again.
- A database integrity conflict during accession registration is translated into HTTP `409` with a message pointing maintainers to `accession_registry`.

### Submission prerequisites and validation

- The current broker validation and claim code resolves existing prerequisite accessions from `accession_registry`, not only from payload fields (`_extract_broker_prerequisites()` in `app/api/v1/endpoints/broker.py`).
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

Note: while Canopy stores ToLIDs, and keeps track of ToLID requests, the action of retrying tolids in "pending" state needs to be handled seperately.

### Submission lifecycle rules outside broker.py

- Organism creation creates draft `project_submission` rows immediately.
- Sample creation creates one draft `sample_submission`.
- Experiment creation creates one draft `experiment_submission`.
- Assembly QC reporting creates one draft `qc_read_submission`.
- Sample and experiment edits can create replacement draft submission rows as described in `system_overview.md`.
