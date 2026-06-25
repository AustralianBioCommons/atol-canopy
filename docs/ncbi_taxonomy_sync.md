## NCBI taxonomy sync behavior

This document describes the current application-level behavior for organism scientific names and NCBI taxonomy enrichment.

### Field roles

`organism.bpa_scientific_name`
- Scientific name supplied by the caller / BPA source payload.

`taxonomy_info.ncbi_scientific_name`
- Scientific name returned by the NCBI taxonomy lookup.

`organism.scientific_name`
- Canonical app-facing scientific name.
- This is a derived field maintained by application logic.

`taxonomy_info.ncbi_last_synced_at`
- Timestamp of the latest successful NCBI sync.
- Only updated when an NCBI lookup succeeds and returns mapped taxonomy data.

### Canonical scientific name rule

The canonical rule is:

```text
organism.scientific_name =
    taxonomy_info.ncbi_scientific_name if present
    else organism.bpa_scientific_name
```

This rule is recomputed during relevant writes instead of using a one-time copy or "set if null" behavior.

### Current write behavior

#### Organism create

When a new organism is created:
- `organism.bpa_scientific_name` is stored from the caller payload
- `organism.scientific_name` is initially set to `bpa_scientific_name`

#### Organism update

When an organism is updated:
- BPA/source fields are updated
- `organism.scientific_name` is recomputed
- if related `taxonomy_info.ncbi_scientific_name` exists, it still takes precedence

#### TaxonomyInfo create

When `taxonomy_info` is created:
- the service performs an NCBI taxonomy lookup
- mapped NCBI fields are stored on `taxonomy_info`
- `taxonomy_info.ncbi_last_synced_at` is set to the current timestamp
- `organism.scientific_name` is recomputed using the canonical rule

#### TaxonomyInfo bulk import

When `taxonomy_info` is bulk imported:
- taxon IDs are collected first
- NCBI lookup is performed in batches
- mapped NCBI fields are stored per row
- new rows are only created when NCBI enrichment succeeds
- rows left behind from an earlier partial import with no successful NCBI sync are retried on rerun
- `taxonomy_info.ncbi_last_synced_at` is set for successfully mapped rows
- `organism.scientific_name` is recomputed per organism

#### TaxonomyInfo delete

When `taxonomy_info` is deleted:
- `organism.scientific_name` falls back to `organism.bpa_scientific_name`

### Current endpoint semantics

`POST /api/v1/organisms`
- Creates organism rows and related project records.
- Does not trigger NCBI taxonomy enrichment.

`POST /api/v1/taxonomy-info`
- Creates a taxonomy info row and performs NCBI enrichment.

`POST /api/v1/taxonomy-info/bulk-import`
- Bulk creates taxonomy info rows and performs batched NCBI enrichment.
- If NCBI enrichment fails for a new row, that row is skipped instead of creating an empty placeholder.
- If a prior run created a row without a successful NCBI sync, rerunning bulk import retries that row.
- The bulk response includes `ncbi_retryable_count` and `ncbi_retryable_taxon_ids` so callers can distinguish retryable NCBI lookup misses from other skipped rows.

At the moment, the taxonomy-info create/bulk-import flows are treated as insert-oriented paths rather than explicit upsert endpoints.

### Caller-owned vs NCBI-owned fields

Callers should not provide `ncbi_*` fields in taxonomy-info request payloads.

Those fields are lookup-owned and come from the NCBI enrichment step. This is enforced by the taxonomy-info write schemas.

### Temporary organism field compatibility shim

The API is in a transition period where some callers still send legacy organism field names without the `bpa_` prefix.

Current temporary input mapping:
- `scientific_name -> bpa_scientific_name`
- `genus -> bpa_genus`
- `species -> bpa_species`
- `common_name -> bpa_common_name`
- `infraspecific_epithet -> bpa_infraspecific_epithet`
- `culture_or_strain_id -> bpa_culture_or_strain_id`
- `authority -> bpa_authority`

This compatibility exists in two places:

1. `app/schemas/organism.py`
- The Pydantic write schema maps legacy input fields to `bpa_*` fields before validation.

2. `app/services/organism_service.py`
- The raw `bulk_import_organisms(...)` path applies the same legacy fallbacks because it bypasses the organism Pydantic schema.

### Cleanup once callers are updated

Once all callers send only `bpa_*` organism fields, remove:

1. The legacy field coercion validator in `app/schemas/organism.py`
2. The legacy fallback reads in `app/services/organism_service.py` bulk import

These sections are marked with `TODO` comments in the code.

### Why this design was chosen

This design keeps:
- provenance fields separate (`bpa_scientific_name`, `ncbi_scientific_name`)
- one canonical field for the rest of the app (`organism.scientific_name`)
- application logic simple for read paths that need a single scientific name

It also avoids hidden state by always recomputing the canonical field from a deterministic precedence rule.
