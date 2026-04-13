# Database Migrations

## Normalized Accession Lookups Migration

This directory contains migration scripts to refactor submission tables to use normalized accession lookups instead of denormalized accession columns.

### Overview

Previously, prerequisite accessions were stored in denormalized columns:
- `experiment_submission.project_accession`
- `experiment_submission.sample_accession`
- `read_submission.experiment_accession`

Now, accessions are looked up from `accession_registry` via FK relationships:
- `sample_submission.project_id` → lookup project accession
- `experiment_submission.sample_id` → lookup sample accession
- `experiment_submission.project_id` → lookup project accession
- `read_submission.experiment_id` → lookup experiment accession

### Benefits

1. **No backfill complexity** - When a prerequisite gets an accession, all dependent submissions automatically see it via join
2. **Single source of truth** - Accessions only stored in `accession_registry`
3. **Always current** - Lookups always return the latest accession
4. **Simpler maintenance** - No need to update multiple tables

### Migration Steps

#### 1. Add FK Columns (Safe to run on production)

```bash
docker compose exec db psql -U atol_user -d atol_db -f /migrations/add_submission_fk_columns.sql
```

This script:
- Adds `sample_submission.project_id` FK column
- Backfills `project_id` from `sample.project_id`
- Makes `project_id` NOT NULL
- Adds index for performance
- Makes `experiment_submission.project_id` and `read_submission.project_id` nullable

#### 2. Deploy Application Code

Deploy the updated application code that uses normalized accession lookups:
- Updated `_extract_broker_prerequisites()` to lookup from `accession_registry`
- Updated `_build_contract_entity()` to accept `db` parameter
- Updated ORM models to remove denormalized columns

#### 3. Remove Denormalized Columns (Run after code deployment)

```bash
docker compose exec db psql -U atol_user -d atol_db -f /migrations/remove_denormalized_accession_columns.sql
```

This script:
- Drops FK constraints for denormalized columns
- Drops the denormalized accession columns

### Rollback Plan

If you need to rollback:

1. **Before removing denormalized columns**: Simply redeploy the old application code
2. **After removing denormalized columns**: You'll need to:
   - Recreate the denormalized columns
   - Backfill them from `accession_registry`
   - Recreate FK constraints
   - Redeploy old application code

### Testing

After migration, verify prerequisites are populated correctly:

```bash
# Test the /claims/ready endpoint
curl -X POST http://localhost:8000/api/v1/broker/claims/ready \
  -H "Content-Type: application/json" \
  -d '{"tax_id": "9606"}'

# Test the /claims/batch endpoint
curl -X POST http://localhost:8000/api/v1/broker/claims/batch \
  -H "Content-Type: application/json" \
  -d '{"sample_ids": ["<uuid>"]}'

# Verify prerequisites are populated (not null) when accessions exist
```

### Schema Changes Summary

**sample_submission:**
- ✅ Added: `project_id UUID NOT NULL REFERENCES project(id)`
- ✅ Added: Index on `project_id`

**experiment_submission:**
- ❌ Removed: `project_accession TEXT`
- ❌ Removed: `sample_accession TEXT`
- ❌ Removed: FK constraints `fk_proj_acc`, `fk_samp_acc`

**read_submission:**
- ❌ Removed: `experiment_accession TEXT`
- ❌ Removed: FK constraint `fk_exp_acc`

### Code Changes Summary

**Broker API (`app/api/v1/endpoints/broker.py`):**
- Added `_get_accession_for_entity()` helper function
- Updated `_extract_broker_prerequisites()` to accept `db` parameter and lookup accessions
- Updated `_build_contract_entity()` to accept `db` parameter
- Updated all callers to pass `db` parameter

**ORM Models:**
- `app/models/sample.py`: Added `project_id` column
- `app/models/experiment.py`: Removed `project_accession`, `sample_accession` columns and FK constraints
- `app/models/read.py`: Removed `experiment_accession` column and FK constraint
