# Bulk Import Workflows

This document describes the bulk-import endpoints that are active in the current codebase.

## Verified

### Active bulk-import endpoints

| Method | Endpoint | Expected top-level payload shape | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/v1/organisms/bulk-import` | raw dictionary keyed by `taxon_id` | No wrapper key such as `organisms` |
| `POST` | `/api/v1/samples/bulk-import` | raw dictionary keyed by `bpa_sample_id` | Mixed sample import path; defaults to specimen unless `kind` supplied |
| `POST` | `/api/v1/samples/bulk-import-specimens` | raw dictionary keyed by `taxon_id`, then `specimen_id` | Explicit specimen-only import |
| `POST` | `/api/v1/samples/bulk-import-derived` | raw dictionary keyed by sample key | Explicit derived-only import |
| `POST` | `/api/v1/experiments/bulk-import` | raw dictionary keyed by package ID | Can also create `read` rows from nested `runs` lists |
| `POST` | `/api/v1/taxonomy-info/bulk-import` | raw dictionary keyed by `taxon_id` | Insert-oriented, with NCBI enrichment |
| `POST` | `/api/v1/taxonomy-info/bulk-upsert` | raw dictionary keyed by `taxon_id` | Insert or update, with NCBI enrichment |
| `POST` | `/api/v1/taxonomy-info/bulk-ncbi-refresh` | object with `taxon_ids` list | Refresh existing taxonomy-info rows only |

### Authentication and roles

- Organism bulk import requires `organisms:bulk_import`.
- Sample bulk import endpoints require `samples:bulk_import`.
- Experiment bulk import requires `experiments:bulk_import`.
- Taxonomy bulk actions require the matching taxonomy policies defined in `app/core/policy.py`.

### Recommended import order

1. Organisms
   -  `transform_data/unique_organisms.jsonl.gz` -> `/api/v1/organisms/bulk-import`
   -  `organism_info/organism_reference_data.json` -> `/api/v1/taxonomy-info/bulk-upsert`
3. Specimen samples
   - `transform_data/specimens_output.json.gz` -> `/api/v1/samples/bulk-import-specimens`
5. Derived samples
   - `transformed.jsonl.gz` -> `/api/v1/samples/bulk-import-derived`
7. Experiments
   - `transform_data/experiments_output.json.gz` -> `/api/v1/experiments/bulk-import`
9. Assembly intents or broker-driven submission workflows
10. Taxonomy-info import or refresh when NCBI enrichment is needed

This ordering is verified from the code-level dependencies:

- samples require existing organisms
- experiments require existing samples and the organism’s `genomic_data` project
- taxonomy info requires existing organisms

## Endpoint-specific behavior

### `POST /api/v1/organisms/bulk-import`

- Creates new `organism` rows.
- Also creates the paired `root` and `genomic_data` `project` rows plus draft `project_submission` rows for each organism.
- Skips rows when the organism already exists.
- Accepts both current `bpa_*` fields and legacy unprefixed fields for several organism attributes.

Example payload:

```json
{
  "172942": {
    "taxon_id": 172942,
    "bpa_scientific_name": "Example species"
  }
}
```

### `POST /api/v1/samples/bulk-import-specimens`

- Expects nested keys: outer `taxon_id`, inner `specimen_id`.
- Enforces one specimen sample per `(taxon_id, specimen_id)`.
- Forces `organism_part` to `"WHOLE ORGANISM"` in this explicit specimen import path.

Example payload:

```json
{
  "172942": {
    "SPEC-001": {
      "bpa_sample_id": "BPA-SPEC-001",
      "lifestage": "adult"
    }
  }
}
```

### `POST /api/v1/samples/bulk-import-derived`

- Requires `bpa_sample_id`.
- Requires `taxon_id`.
- Requires `specimen_id` so the code can find the parent specimen sample.
- Parent lookup is by `(taxon_id, specimen_id)` with `kind = specimen`.

### `POST /api/v1/samples/bulk-import`

- Accepts a flatter legacy/importer-friendly path keyed by `bpa_sample_id`.
- Defaults missing required text fields such as `lifestage`, `sex`, and `habitat` to `"unknown"` in code.
- Defaults sample kind to `specimen` unless `kind` is supplied.

### `POST /api/v1/experiments/bulk-import`

- Requires `bpa_sample_id` in each experiment payload so the sample can be resolved.
- Requires `bpa_library_id`.
- Creates `experiment` and `experiment_submission` rows.
- If a `runs` list exists, the importer also creates `read` rows.
- If the experiment already exists, the importer still attempts to create any missing reads from the nested `runs` list.

### Taxonomy bulk operations

- `bulk-import` skips already-fully-synced rows and only creates new rows when NCBI enrichment returns mapped data.
- `bulk-upsert` can insert or update rows and re-fetches NCBI data for all supplied taxon IDs.
- `bulk-ncbi-refresh` updates only existing `taxonomy_info` rows.

## Important constraints and sharp edges

- The organism, sample, and experiment bulk endpoints do not share one uniform payload shape.
- Several bulk paths still contain compatibility logic for older field names or older caller behavior.
- Some bulk paths emit partial diagnostics through response `errors`; some older code paths also still use `print(...)` for local debugging.

## Unknown From This Repo

- There are no canonical example input files in the tracked repository proving the exact upstream export format for every current caller.
- The repo does not document who owns the promotion from imported `draft` submission rows to `ready`.
