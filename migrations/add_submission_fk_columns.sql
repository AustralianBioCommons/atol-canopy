-- Migration: Add FK columns to submission tables for normalized accession lookups
-- This migration adds foreign key columns to link submissions to their prerequisite entities
-- Accessions will be looked up from accession_registry instead of being denormalized

-- Step 1: Add project_id FK to sample_submission (if it doesn't exist)
ALTER TABLE sample_submission
  ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES project(id);

-- Step 2: Backfill project_id from organism's genomic_data project
UPDATE sample_submission ss
SET project_id = p.id
FROM sample s
JOIN project p ON p.organism_key = s.organism_key AND p.project_type = 'genomic_data'
WHERE ss.sample_id = s.id
  AND ss.project_id IS NULL;

-- Step 3: Make project_id NOT NULL (now that it's backfilled)
ALTER TABLE sample_submission
  ALTER COLUMN project_id SET NOT NULL;

-- Step 4: Add index for performance
CREATE INDEX IF NOT EXISTS idx_sample_submission_project_id ON sample_submission(project_id);

-- Step 5: Make experiment_submission.project_id nullable (it's derived via sample)
ALTER TABLE experiment_submission
  ALTER COLUMN project_id DROP NOT NULL;

-- Step 6: Make read_submission.project_id nullable (it's derived via experiment)
ALTER TABLE read_submission
  ALTER COLUMN project_id DROP NOT NULL;

-- Note: We'll remove denormalized accession columns in a separate migration
-- after updating the application code to use lookups
