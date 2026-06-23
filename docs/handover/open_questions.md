# Open Questions And Tribal Knowledge Gaps

## Unresolved Questions For The Human Owner

1. Which broker API surface is actually used in production today: the flat contract (`/broker/claims/*`, `/broker/reports/{attempt_id}`) or the older organism/attempt endpoints?
2. What process promotes submission rows from `draft` to `ready`? I could not verify any code path in this repo that sets `status = "ready"` for project, sample, experiment, or QC-read submissions.
3. Which payload shapes are treated as canonical for bulk organism, sample, and experiment imports outside the request validation implied by this repo?
4. Is `POST /api/v1/assemblies/from-experiments/{taxon_id}` still an active workflow, or has the assembly intent flow replaced it operationally?
5. Should stale historical documents under `data/docs/` remain in the repo, or should they be archived elsewhere to avoid confusing maintainers?
6. What are the expected roles and minimum permissions for day-to-day maintainer accounts versus broker accounts versus genome-launcher accounts?
7. Are there manual post-deploy checks, rollback steps, or data-backup requirements that happen outside the GitHub Actions workflows?

## High-Risk Tribal Knowledge Not Present In The Repo

### Verified gaps

- Production deployment topology is not documented. The repo shows ECR image publishing and Lambda-triggered deployment automation, but not the runtime environment or rollback procedure.
- Broker client behavior is not documented. The repo exposes broker contracts, but not the external worker implementation, retry policy, or release cadence.
- ToLID remote-service details are not documented. The repo stores ToLID state and exposes report endpoints, but the external request payload, retry rules, and error taxonomy are absent.
- Data-ingest source contracts are not documented. The repo contains code that accepts bulk organism/sample/experiment dictionaries, but not the upstream ownership or canonical sample files.
- The governance around `ready` status is absent. This is operationally important because broker claim behavior differs between the older and newer broker endpoints.

### Inferences

- Maintainers probably rely on conventions outside this repo for deciding when staged submission payloads are safe to send to the broker, because the code models `ready` but does not create it.

### Unknown From This Repo

- Which stale routes, docs, or backward-compatibility shims can be safely removed without breaking external callers.
- Whether production operators depend on direct database edits for emergency recovery.
