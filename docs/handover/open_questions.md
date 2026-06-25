# Open Questions And Tribal Knowledge Gaps

## Unresolved Questions For The Human Owner

1. What process promotes submission rows from `draft` to `ready`? I could not verify any code path in this repo that sets `status = "ready"` for project, sample, experiment, or QC-read submissions.
2. Which payload shapes are treated as canonical for bulk organism, sample, and experiment imports outside the request validation implied by this repo?
3. Is `POST /api/v1/assemblies/from-experiments/{taxon_id}` still an active workflow, or has the assembly intent flow replaced it operationally?
4. What are the expected roles and minimum permissions for day-to-day maintainer accounts versus broker accounts versus genome-launcher accounts?
5. Are there manual post-deploy checks, rollback steps, or data-backup requirements that happen outside the GitHub Actions workflows?

## High-Risk Tribal Knowledge Not Present In The Repo

### Verified gaps

- Production deployment topology is not documented. The repo shows ECR image publishing and Lambda-triggered deployment automation, but not the runtime environment or rollback procedure.
- Broker client behavior is not documented. The repo exposes broker contracts, but not the external worker implementation, retry policy, or release cadence.
- ToLID remote-service details are not documented. The repo stores ToLID state and exposes report endpoints, but the external request payload, retry rules, and error taxonomy are absent.
- Data-ingest source contracts are not documented. The repo contains code that accepts bulk organism/sample/experiment dictionaries, but not the upstream ownership or canonical sample files.
- The governance around `ready` status is absent. This is operationally important because the routed broker claim contract accepts both `draft` and `ready`, while retained legacy helper code only queries `draft`.

### Inferences

- Maintainers probably rely on conventions outside this repo for deciding when staged submission payloads are safe to send to the broker, because the code models `ready` but does not create it.

### Unknown From This Repo

- Whether the retained non-routed legacy broker helper functions can be deleted outright without losing useful maintenance tooling.
- Whether production operators depend on direct database edits for emergency recovery.
