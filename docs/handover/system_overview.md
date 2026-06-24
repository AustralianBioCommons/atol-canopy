# System Overview

### What the Canopy app does

- The application is a FastAPI backend with a versioned API under `/api/v1` (`app/main.py`, `app/api/v1/api.py`).
- It stores 1) biological metadata imported from BPA, 2) submission-ready metadata objects for ENA and tracking of these submissions, 3) inputs and outputs for AToL's genome engine workflow (incl. qc, genome assembly and post-assembly pipelines). The key entities are:
  - organisms and taxonomy information
  - samples and sample lineage
  - experiments and raw reads
  - QC-read results
  - assemblies, assembly runs, and assembly stage runs
  - projects, genome notes*, and users
  - broker submission objects, broker submission events, and ToLID request state
- Submission-facing entities use a main-table plus submission-table pattern for at least projects, samples, experiments, QC reads, and assemblies (`app/models/project.py`, `sample.py`, `experiment.py`, `qc_read.py`, `assembly.py`).

### Codebase structure

| Path | Verified role |
| --- | --- |
| `app/main.py` | FastAPI app creation, CORS setup, exception handlers, root, health, version |
| `app/api/v1/api.py` | Registers all active routers |
| `app/api/v1/endpoints/` | Route handlers and some light business rules *(should ideally move all business ogic to services)* |
| `app/models/` | SQLAlchemy models for tables and relationships |
| `app/schemas/` | Pydantic request/response models and enums |
| `app/services/` | Shared business logic for organism, experiment, taxonomy, assembly, broker-adjacent helpers, and ToLID state |
| `app/core/` | settings, auth dependencies, password/JWT helpers, pagination, policy wrapper, app error types |
| `app/config/ena-atol-map.json`** | ENA payload field mapping used by sample and experiment payload generation |
| `alembic/` | Schema migration entrypoint and revisions |
| `scripts/` | Container startup, lease-expiry helper, and user-creation script |
| `tests/` | Unit tests for routes, services, settings, security, and broker behavior |

** This must be updated if either the AToL schema and/or ENA's ToL sample checklist [ERC000053](https://www.ebi.ac.uk/ena/browser/view/ERC000053) change.
### Entity and lifecycle patterns

#### Organisms

- Creating an organism also creates two `project` rows, one `root` and one `genomic_data`, plus matching `project_submission` draft rows (`app/services/organism_service.py`).
- `organism.scientific_name` is treated as the app-facing canonical name and is recomputed from `taxonomy_info.ncbi_scientific_name` when that exists; otherwise it falls back to `organism.bpa_scientific_name` (`app/services/organism_service.py`, `app/services/taxonomy_info_service.py`).

#### Samples

- Samples support `specimen` and `derived` kinds (`app/schemas/common.py`, `app/models/sample.py`).
- Derived samples must point to a specimen parent in the same `taxon_id`; specimen samples cannot have a parent (`app/api/v1/endpoints/samples.py`).
- Creating a sample also creates a draft `sample_submission` linked to the organism’s `genomic_data` project (`app/api/v1/endpoints/samples.py`).

#### Experiments and reads

- Creating an experiment requires an existing sample and the sample’s `genomic_data` project; it also creates a draft `experiment_submission` with `prepared_payload` built from `app/config/ena-atol-map.json` (`app/services/experiment_service.py`).
- Bulk experiment import also creates `read` rows from nested `runs` payloads (`app/services/experiment_service.py`).

#### Taxonomy enrichment

- Taxonomy-info create, bulk-import, bulk-upsert, and bulk-refresh all call NCBI lookup code in `app/services/ncbi_taxonomy_service.py` through `app/services/taxonomy_info_service.py`.
- Successful NCBI enrichment updates `taxonomy_info.ncbi_last_synced_at`, recomputes `organism.scientific_name`, and refreshes draft/ready project submission payloads for that organism (`app/services/taxonomy_info_service.py`, `app/services/organism_service.py`).
- Note: the bulk-insert endpoint sometimes returns before enriching all requested The endpoint is indopodent: so simply re-run the command until no more empty rows are returned.

#### Assemblies

- There are two assembly creation flows:
  - generic `POST /api/v1/assemblies/`
  - intent-driven `POST /api/v1/assemblies/intent/{taxon_id}`
- The intent flow validates specimen samples, resolves lineage-linked experiments and reads, generates a manifest JSON, stores it on the `assembly`, and returns `assembly_id`, `version`, and the manifest (`app/api/v1/endpoints/assemblies.py`, `app/services/assembly_helper.py`).
- "Assembly runs" (`assembly_run` table in db) represent a pipeline invocation for a specific assembly/manifest and are tracked/identified by `github_repo` plus `git_commit` (i.e. used to report results for different runs of the same assembly); "assembly stage runs" (`aasembly_stage_run` table in db) store one record per stage name per run (`app/models/assembly.py`, `app/services/assembly_service.py`).
- QC read reporting for assemblies creates `qc_read`, `qc_read_file`, `qc_read_assembly`, and a draft `qc_read_submission` (`app/api/v1/endpoints/assemblies.py`, `app/api/v1/endpoints/qc_reads.py`).
- Assembly stage reporting for assemblies accepts a flexible `data` object and a list of files. NOTE: at the moment, you can only report results for an assembly stage run via the POST /assemblies/{assembly_id}/runs/{run_id}/stage_runs/{stage_run_id} endpoint *once*, reporting more results will fail, and the respective PATCH endpoint will replace the existing files rather than appending them. (TODO: this should be fixed to allow appending files)

#### Submission tables and status changes

- Create paths for core objects (projects, samples, experiments, qc_reads) generally produce `draft` submission rows in the respective `*_submission` tables.
- Sample and experiment updates have status-aware behavior:
  - `submitting`: update blocked
  - `draft` or `ready`: existing submission row updated in place and reset to `draft`
  - `accepted`: existing submission row marked `replaced`, then a new `draft` row is created preserving accession fields
  - `rejected` or `replaced`: a new `draft` row is created preserving accession fields where present
  (`app/api/v1/endpoints/samples.py`, `app/services/experiment_service.py`)

### External interaction points visible in code

- Broker-facing submission APIs live in `app/api/v1/endpoints/broker.py`.
- ToLID durable state is exposed through broker routes but handled by `app/services/tolid_service.py`.
- NCBI taxonomy lookup is the only outbound HTTP integration directly evidenced in application code (`app/services/ncbi_taxonomy_service.py`).

## Notes

- Canopy is a metadata store and broker-facing coordination service. It doesn't directly interact with ENA servers. Rather, it provides the data needed for submission, which is requested and submitted by a seperate ENA broker service and then reported back to Canopy (including, importantly, the accessions of submitted objects).

## To check

- Whether `POST /api/v1/assemblies/from-experiments/{taxon_id}` is still actively used now that the assembly intent flow exists.
