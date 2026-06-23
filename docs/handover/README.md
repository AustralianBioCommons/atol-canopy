# Canopy Handover Pack

## Verified

This handover pack was written from the current repository state, with the code, tests, migrations, scripts, and selected current docs treated as the source of truth.

Use these files in this order:

1. `doc_audit.md`
2. `system_overview.md`
3. `setup_and_operations.md`
4. `broker_and_submission_flows.md`
5. `config_reference.md`
6. `troubleshooting.md`
7. `open_questions.md`

## Proposed Documentation Structure

| File | Purpose |
| --- | --- |
| `docs/handover/README.md` | Entry point for the handover pack |
| `docs/handover/doc_audit.md` | Audit of existing docs, README, Postman, and generated notes |
| `docs/handover/system_overview.md` | What the system does, repo structure, key entities, main lifecycle rules |
| `docs/handover/setup_and_operations.md` | Local setup, Docker flow, Alembic flow, scripts, recurring operator tasks |
| `docs/handover/broker_and_submission_flows.md` | Submission table lifecycle, broker claims/reports, ToLID flow, assembly reporting handoff points |
| `docs/handover/config_reference.md` | Environment variables and config behavior derived from code |
| `docs/handover/troubleshooting.md` | Maintainer symptom-driven troubleshooting guide |
| `docs/handover/open_questions.md` | Questions for the human owner and tribal knowledge gaps not captured in the repo |

## Unknown From This Repo

- Which broker endpoints are used in production versus retained only for backward compatibility.
- Which human or external process promotes submission rows from `draft` to `ready`.
- The production runtime topology behind the GitHub Actions deployment automation.
