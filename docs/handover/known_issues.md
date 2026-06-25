# Known Issues And Outstanding Work

## TO DO: Canopy & Broker

- Persist broker logs and broker error responses so they can be reviewed later.

- Persist BPA import logs, mapper outputs, and bulk-import failures. Bulk import endpoints return error lists, but import history is not stored. (side note, some sample import paths still use `print(...)` rather than structured logging e.g. in [samples.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/samples.py))

- Decide whether `bpa_package_id` should stay in the request body for `POST /api/v1/assemblies/{assembly_id}/qc-reads/report`. It is currently a required body field in [qc_read.py](/Users/emilylm/Repositories/atol-database-v2/app/schemas/qc_read.py) and is resolved in [assemblies.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/assemblies.py). From PO feedback, `bpa_package_id` should be moved to a path variable.

- Broker support for parent and child projects is missing. There is no project hierarchy model or broker payload support in [project.py](/Users/emilylm/Repositories/atol-database-v2/app/models/project.py) or [broker.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/broker.py). We were awaiting confirmation from ENA about how to register and confirm parent-child project relos. Need to confirm this and implement the heirarchy.

- Assembly stage reporting is one-shot per `(assembly_run_id, stage_name)`. A second `POST` for the same stage returns a conflict. `PATCH` replaces the file list; it does not append. See [assembly_service.py](/Users/emilylm/Repositories/atol-database-v2/app/services/assembly_service.py). This is likely undesirable - may want to update so that we can add more result files and/or metadata for an assembly stage we have already reported results for.

- `POST /api/v1/assemblies/{assembly_id}/qc-reads/report` always creates a new `QcRead`, new files, and a new draft `QcReadSubmission`. There is no deduplication, uniqueness check, or delete path inside that workflow. See [assemblies.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/assemblies.py). May need to change this behaviour if we want more control.

- ToLID external-id selection should be reviewed. [tolid_service.py](/Users/emilylm/Repositories/atol-database-v2/app/services/tolid_service.py) currently uses `SampleSubmission.accession` and only falls back to `sample.biosample_accession`. We actually want to use the external / BioSample accession as the `external_id` for the ToLIDs we register -> so we need to change this (may require changes to the broker)

- Project titles are not validated against any ENA minimum length in Canopy. Recent submission attempts (using the broker) have revealed that ENA requires titles of at least 20 characters. That check should be added in [project.py](/Users/emilylm/Repositories/atol-database-v2/app/schemas/project.py) or before broker submission. May need to pad `title` field when char length is too short.

- The current `qc-reads/report` payload is inconsistent with the genome launcher. The current Canopy request shape is defined in [qc_read.py](/Users/emilylm/Repositories/atol-database-v2/app/schemas/qc_read.py). The genome launcher has different fields for qc_read files. Need to change fields in Canopy, or in the genome launcher - or a shim could be added.

- Annotationa are not implemented.

- Genome notes are largely not implemented. There exists separate CRUD and rudimentary publish/unpublish feature in [genome_notes.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/genome_notes.py) and [genome_note.py](/Users/emilylm/Repositories/atol-database-v2/app/models/genome_note.py), but this hasn't been tested or properly implemented. We need to implement endpoints that 1) return the metadata required for a genome note and 2) allow reporting/storing of a published genome note back into the db (might be the actual genome note data or just a DOI/link).

- Ensure all API endpoints have explicit `@policy(...)` protection. Several authenticated endpoints still rely only on authentication and have no policy decorator.

- Remove the hard-coded repository path from [create_user.py](/Users/emilylm/Repositories/atol-database-v2/scripts/create_user.py). All script sin `scripts/` folder can probably be removed and managed elsewhere.

## TODO: Operations

- Set up a scheduler to import data from BPA data portal.

- Set up a scheduler for retrying or polling `pending` ToLID requests. =

- Define log collection and log retention for deployed environments. Logs are available in AWS CloudWatch.

- Set up scheduled database backup, dump, and restore procedures.

- When prod environment created, dev db should be refreshed from prod db snapshots regularly.. Something to discuss with BioCloud team (will need to decide on & implement a DR protocol)

## Data And Access Management

- Backfill `experiment.bioplatforms_base_url` where it is missing in existing environments (missing in dev AWS environment currently - because it is read from BPA data which had already been imported).

- Patch manually assigned ToLIDs for the benchmarking datasets if those records must exist in Canopy. (can use the `/tolid/report` endpoint)

- New roles should be created for 1) each service user (genome launcher and broker) and 2) admin and/or curator users for AToL team members who need to interact with the database. Credentials should be kept confidential. Supported roles in code include `admin`, `curator`, `broker`, `genome_launcher`, and `superuser`.

## Open Questions

- How can ENA parent and child project relationships be verified for private / unreleased projects?

- How long are deployed Canopy logs retained in AWS?

- Does the dev environment still need `bioplatforms_base_url` backfill and manual ToLID backfill?

## Resolved since docs creted

- Duplicate `assembly_run` registration is now handled. Creating the same `(assembly_id, github_repo, git_commit)` combination returns `409` through [assemblies.py](/Users/emilylm/Repositories/atol-database-v2/app/api/v1/endpoints/assemblies.py) and [assembly_service.py](/Users/emilylm/Repositories/atol-database-v2/app/services/assembly_service.py).
