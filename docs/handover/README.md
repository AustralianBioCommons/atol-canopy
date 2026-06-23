# Canopy Handover Pack

This directory contains hander documentation for future maintainers of the Canopy codebase

## What is covered

The docs cover:

- what the system currently does
- where major workflows live in the code
- how local setup and migrations work
- how broker and ToLID flows behave
- deployment to AWS (basic details only - this is largely managed by the BioCloud team)
- manual overrides when things don't go to plan
- where the known gaps and human-owned unknowns still are

This pack is intentionally maintainer-oriented. It favors verified behavior and operator tasks over broad narrative description.

## Recommended Reading Order

1. [system_overview.md](/Users/emilylm/Repositories/atol-database-v2/docs/handover/system_overview.md)
2. [setup_and_operations.md](/Users/emilylm/Repositories/atol-database-v2/docs/handover/setup_and_operations.md)
3. [broker_and_submission_flows.md](/Users/emilylm/Repositories/atol-database-v2/docs/handover/broker_and_submission_flows.md)
4. [config_reference.md](/Users/emilylm/Repositories/atol-database-v2/docs/handover/config_reference.md)
5. [troubleshooting.md](/Users/emilylm/Repositories/atol-database-v2/docs/handover/troubleshooting.md)
6. [open_questions.md](/Users/emilylm/Repositories/atol-database-v2/docs/handover/open_questions.md)

## Document Map

| File | What it covers | When to use it |
| --- | --- | --- |
| [system_overview.md](/Users/emilylm/Repositories/atol-database-v2/docs/handover/system_overview.md) | Repo structure, core entities, main lifecycle patterns, and external interaction points | Use this first when orienting a new maintainer |
| [setup_and_operations.md](/Users/emilylm/Repositories/atol-database-v2/docs/handover/setup_and_operations.md) | Docker startup path, local non-Docker workflow, migrations, scripts, and recurring operator actions | Use this for local setup and day-to-day maintenance |
| [broker_and_submission_flows.md](/Users/emilylm/Repositories/atol-database-v2/docs/handover/broker_and_submission_flows.md) | Submission states, broker claim/report behavior, ToLID flow, and attempt leasing | Use this when debugging broker-facing workflows |
| [config_reference.md](/Users/emilylm/Repositories/atol-database-v2/docs/handover/config_reference.md) | Environment variables and workflow-level config surfaced by the repo | Use this when wiring environments or checking startup failures |
| [troubleshooting.md](/Users/emilylm/Repositories/atol-database-v2/docs/handover/troubleshooting.md) | Symptom-driven maintainer guide | Use this during incidents or confusing behavior |
| [open_questions.md](/Users/emilylm/Repositories/atol-database-v2/docs/handover/open_questions.md) | Gaps that require human knowledge outside the repo | Use this when deciding what tribal knowledge still needs to be captured |

## Relationship To The Top-Level README

- [README.md](/Users/emilylm/Repositories/atol-database-v2/README.md) is the repository’s central high-level document.
- This handover pack is the deeper maintainer set.
- The two should stay consistent, but they serve different depths:
  - `README.md`: complete high-level repo document
  - `docs/handover/`: detailed maintainer and operator documentation

## Highest-Risk Gaps Still Not Solved By Documentation Alone

These are verified as unresolved from the repo itself:

- which broker endpoint family is authoritative in production
- which human or external process moves submission rows from `draft` to `ready`
- what the production runtime topology is behind the GitHub Actions deployment workflows

Those gaps are tracked in [open_questions.md](/Users/emilylm/Repositories/atol-database-v2/docs/handover/open_questions.md).
