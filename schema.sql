-- PostgreSQL schema for biological metadata tracking system
-- Based on ER diagram and requirements

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create ENUM types
CREATE TYPE submission_status AS ENUM ('draft', 'ready', 'submitting', 'rejected', 'accepted', 'replaced');
CREATE TYPE authority_type AS ENUM ('ENA', 'NCBI', 'DDBJ');
CREATE TYPE molecule_type AS ENUM ('genomic DNA', 'genomic RNA');
CREATE TYPE assembly_output_file_type AS ENUM ('QC', 'Other'); -- TODO define more specific types as needed
CREATE TYPE entity_type AS ENUM ('organism', 'sample', 'experiment', 'read', 'assembly', 'project');
CREATE TYPE project_type AS ENUM ('root', 'genomic_data', 'assembly');
-- ==========================================
-- Users and Authentication
-- ==========================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    hashed_password TEXT NOT NULL,
    full_name TEXT,
    roles TEXT[] NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ==========================================
-- Authentication refresh tokens table
-- ==========================================

CREATE TABLE refresh_token (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token_hash TEXT NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ==========================================
-- Organism tables
-- ==========================================

-- Main organism table
CREATE TABLE organism (
    grouping_key TEXT PRIMARY KEY,
    tax_id int UNIQUE NOT NULL,
    -- We need to check that the scientific name = the tax id level, because we have a bunch of tax_ids that are the same for organisms which should have a more granular taxid level
    scientific_name TEXT,
    common_name TEXT,
    common_name_source TEXT,
    bpa_json JSONB,
    taxonomy_lineage_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
/*
    -- BPA organism table
    CREATE TABLE organism_bpa (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        organism_id UUID REFERENCES organism(id),
        bpa_json JSONB,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
*/

-- ==========================================
-- Accession registry table
-- ==========================================

CREATE TABLE accession_registry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    authority authority_type NOT NULL,
    accession TEXT NOT NULL UNIQUE,
    secondary_accession TEXT,
    entity_type entity_type NOT NULL,
    entity_id UUID NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (authority, entity_type, entity_id),
    UNIQUE (authority, accession)
);

CREATE UNIQUE INDEX uq_registry_full
  ON accession_registry (accession, authority, entity_type, entity_id);

-- ==========================================
-- project tables
-- ==========================================

-- Main project table
CREATE TABLE project (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organism_key TEXT NOT NULL REFERENCES organism(grouping_key) ON DELETE CASCADE,
    project_type project_type NOT NULL,
    project_accession TEXT UNIQUE,
    study_type TEXT NOT NULL,
    alias TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    centre_name TEXT,
    study_attributes JSONB,
    submitted_at TIMESTAMP,
    status submission_status NOT NULL DEFAULT 'draft',
    authority authority_type NOT NULL DEFAULT 'ENA',
    -- TODO confirm if we want study attributes, and enforece schema for json (or include as seperate table)
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_one_project_type_per_organism
  ON project (organism_key, project_type);

-- Project submission table
CREATE TABLE IF NOT EXISTS project_submission (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    authority authority_type NOT NULL DEFAULT 'ENA',
    status submission_status NOT NULL DEFAULT 'draft',

    prepared_payload JSONB,
    response_payload JSONB,

    accession TEXT,

    -- constant to help the composite FK
    entity_type_const entity_type NOT NULL DEFAULT 'project' CHECK (entity_type_const = 'project'),

    submitted_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- attempt linkage
    attempt_id UUID,
    finalised_attempt_id UUID,

    -- broker lease/claim fields (attempt-scoped)
    lock_acquired_at TIMESTAMP,
    lock_expires_at TIMESTAMP,

    CONSTRAINT fk_self_project_accession
      FOREIGN KEY (accession, authority, entity_type_const, project_id)
      REFERENCES accession_registry (accession, authority, entity_type, entity_id)
      DEFERRABLE INITIALLY DEFERRED
);

-- Only one accepted submission per project+authority with accession
CREATE UNIQUE INDEX IF NOT EXISTS uq_project_one_accepted
  ON project_submission (project_id, authority)
  WHERE status = 'accepted' AND accession IS NOT NULL;

-- Broker claim indexes
CREATE INDEX IF NOT EXISTS idx_project_submission_attempt ON project_submission (attempt_id);
CREATE INDEX IF NOT EXISTS idx_project_submission_finalised_attempt ON project_submission (finalised_attempt_id);

-- ==========================================
-- Sample tables
-- ==========================================

-- Main sample table
CREATE TABLE sample (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organism_key TEXT NOT NULL REFERENCES organism(grouping_key) ON DELETE CASCADE,
    bpa_sample_id TEXT UNIQUE NOT NULL,
    specimen_id TEXT,
    specimen_id_description TEXT,
    identified_by TEXT,
    specimen_custodian TEXT,
    sample_custodian TEXT,
    lifestage TEXT NOT NULL,
    sex TEXT NOT NULL,
    organism_part TEXT NOT NULL,
    region_and_locality TEXT NOT NULL,
    state_or_region TEXT,
    country_or_sea TEXT NOT NULL,
    indigenous_location TEXT,
    latitude FLOAT,
    longitude FLOAT,
    elevation FLOAT,
    depth FLOAT,
    habitat TEXT NOT NULL,
    collection_method TEXT,
    collection_date TEXT,
    collected_by TEXT NOT NULL DEFAULT 'not provided',
    collecting_institution TEXT NOT NULL DEFAULT 'not provided',
    collection_permit TEXT,
    data_context TEXT,
    bioplatforms_project_id TEXT,
    title TEXT,
    sample_same_as TEXT,
    sample_derived_from TEXT,
    specimen_voucher TEXT,
    tolid TEXT,
    preservation_method TEXT,
    preservation_temperature TEXT,
    project_name TEXT,
    biosample_accession TEXT,
    -- bpa_json JSONB NOT NULL,
    -- TODO extensions json field above instead of bpa_json?
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Sample submission table
CREATE TABLE sample_submission (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sample_id UUID NOT NULL REFERENCES sample(id) ON DELETE CASCADE,
    authority authority_type NOT NULL DEFAULT 'ENA',
    prepared_payload JSONB NOT NULL,
    response_payload JSONB,
    accession TEXT,
    biosample_accession TEXT,
    -- TODO undecided whether to keep biosample_accession here or rely on the accession_registry table
    status submission_status NOT NULL DEFAULT 'draft',
    submitted_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- constant to help the composite FK
    entity_type_const entity_type NOT NULL DEFAULT 'sample' CHECK (entity_type_const = 'sample'),

    -- attempt linkage
    attempt_id UUID,
    finalised_attempt_id UUID,

    -- broker lease/claim fields (attempt-scoped)
    lock_acquired_at TIMESTAMP,
    lock_expires_at TIMESTAMP,

    CONSTRAINT fk_self_accession
    FOREIGN KEY (accession, authority, entity_type_const, sample_id)
    REFERENCES accession_registry (accession, authority, entity_type, entity_id)
    DEFERRABLE INITIALLY DEFERRED
);

CREATE UNIQUE INDEX uq_sample_one_accepted
  ON sample_submission (sample_id, authority)
  WHERE status = 'accepted' AND accession IS NOT NULL;
  -- TODO uniqueness constraint above?
    -- TODO consider if we want to keep track of former submissions that have been replaced/modified

-- Broker claim indexes
CREATE INDEX IF NOT EXISTS idx_sample_submission_attempt ON sample_submission (attempt_id);
CREATE INDEX IF NOT EXISTS idx_sample_submission_finalised_attempt ON sample_submission (finalised_attempt_id);

-- UNIQUE (sample_id, authority) WHERE status = 'accepted' AND accession IS NOT NULL

-- ==========================================
-- Experiment tables
-- ==========================================

-- Main experiment table
CREATE TABLE experiment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sample_id UUID NOT NULL REFERENCES sample(id) ON DELETE CASCADE,
    bpa_package_id TEXT UNIQUE NOT NULL,
    design_description TEXT,
    bpa_library_id TEXT,
    library_strategy TEXT,
    library_source TEXT,
    insert_size TEXT,
    library_construction_protocol TEXT,
    library_selection TEXT,
    library_layout TEXT,
    instrument_model TEXT,
    platform TEXT,
    material_extracted_by TEXT,
    library_prepared_by TEXT,
    sequencing_kit TEXT,
    flowcell_type TEXT,
    base_caller_model TEXT,
    data_owner TEXT,
    project_collaborators TEXT,
    extraction_method TEXT,
    nucleic_acid_treatment TEXT,
    extraction_protocol_doi TEXT,
    nucleic_acid_conc TEXT,
    nucleic_acid_volume TEXT,
    gal TEXT,
    raw_data_release_date TEXT,

    -- bpa_dataset_id TEXT UNIQUE NOT NULL,
    -- bpa_json JSONB NOT NULL,
    -- TODO extensions json field above instead of bpa_json?
    -- TO DO perhaps add an 'extensions' field instead of bpa_json
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Experiment submission table
CREATE TABLE experiment_submission (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    experiment_id UUID NOT NULL REFERENCES experiment(id) ON DELETE CASCADE,
    authority authority_type NOT NULL DEFAULT 'ENA',
    status submission_status NOT NULL DEFAULT 'draft',

    sample_id UUID REFERENCES sample(id) NOT NULL, -- nullable if sample doesn't exist yet? or are we happy to have the constraint that a sample & project needs to exist before we create an experiment, probs
    project_id UUID REFERENCES project(id),
    -- TO DO do we even need this ? I don't think so

    project_accession TEXT,
    sample_accession TEXT,

    prepared_payload JSONB,
    response_payload JSONB,

    accession TEXT,

    -- constant to help the composite FK
    entity_type_const entity_type NOT NULL DEFAULT 'experiment' CHECK (entity_type_const = 'experiment'),

    submitted_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    attempt_id UUID,
    finalised_attempt_id UUID,

    -- broker lease/claim fields
    lock_acquired_at TIMESTAMP,
    lock_expires_at TIMESTAMP,

      -- When accession is present, it must exist in the registry AND map to this same experiment:
  CONSTRAINT fk_self_accession
    FOREIGN KEY (accession, authority, entity_type_const, experiment_id)
    REFERENCES accession_registry (accession, authority, entity_type, entity_id)
    DEFERRABLE INITIALLY DEFERRED,

  -- Upstream accessions also validated (drafts allowed to be NULL):
  CONSTRAINT fk_proj_acc
    FOREIGN KEY (project_accession, authority)
    REFERENCES accession_registry (accession, authority),
  CONSTRAINT fk_samp_acc
    FOREIGN KEY (sample_accession, authority)
    REFERENCES accession_registry (accession, authority)
);

-- Broker lease/claim index
CREATE INDEX IF NOT EXISTS idx_experiment_submission_attempt ON experiment_submission (attempt_id);
CREATE INDEX IF NOT EXISTS idx_experiment_submission_finalised_attempt ON experiment_submission (finalised_attempt_id);

-- TODO consider if we want to keep track of former submissions that have been replaced/modified
CREATE UNIQUE INDEX uq_exp_one_accepted
  ON experiment_submission (experiment_id, authority)
  WHERE status = 'accepted' AND accession IS NOT NULL;

/*
    -- When status = accepted, both upstream accessions must be present
    CONSTRAINT chk_ready_to_send
    CHECK (
        status IN ('draft','ready','submitted','rejected')
        OR (project_accession IS NOT NULL AND sample_accession IS NOT NULL AND accession IS NOT NULL)
    )
*/

-- ==========================================
-- Read tables
-- ==========================================

CREATE TABLE read (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    experiment_id UUID NOT NULL REFERENCES experiment(id) ON DELETE CASCADE,
    bpa_resource_id TEXT UNIQUE,
    bpa_dataset_id TEXT,
    file_name TEXT NOT NULL,
    file_checksum TEXT,
    file_format TEXT NOT NULL,
    optional_file BOOLEAN NOT NULL DEFAULT TRUE,
    bioplatforms_url TEXT,
    read_number TEXT,
    lane_number TEXT,
    run_read_count TEXT,
    run_base_count TEXT,
    -- bpa_json JSONB NOT NULL,
    -- TODO extensions json field above instead of bpa_json?
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE read_submission (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    read_id UUID NOT NULL REFERENCES read(id) ON DELETE CASCADE,
    authority authority_type NOT NULL DEFAULT 'ENA',
    status submission_status NOT NULL DEFAULT 'draft',

    prepared_payload JSONB NOT NULL,
    response_payload JSONB,

    experiment_id UUID NOT NULL REFERENCES experiment(id) ON DELETE CASCADE,
    project_id UUID REFERENCES project(id),

    experiment_accession TEXT,

    accession TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- attempt linkage
    attempt_id UUID,
    finalised_attempt_id UUID,

    -- broker lease/claim fields (attempt-scoped)
    lock_acquired_at TIMESTAMP,
    lock_expires_at TIMESTAMP,

    -- constant to help the composite FK
    entity_type_const entity_type NOT NULL DEFAULT 'read' CHECK (entity_type_const = 'read'),

    -- When accession is present, it must exist in the registry AND map to this same experiment:
  CONSTRAINT fk_self_accession
    FOREIGN KEY (accession, authority, entity_type_const, read_id)
    REFERENCES accession_registry (accession, authority, entity_type, entity_id)
    DEFERRABLE INITIALLY DEFERRED,

  -- Upstream accessions also validated (drafts allowed to be NULL):
  CONSTRAINT fk_exp_acc
    FOREIGN KEY (experiment_accession, authority)
    REFERENCES accession_registry (accession, authority)
);

CREATE UNIQUE INDEX uq_read_one_accepted
  ON read_submission (read_id, authority)
  WHERE status = 'accepted' AND accession IS NOT NULL;

-- Broker lease/claim index
-- removed batch index; attempt-only
CREATE INDEX IF NOT EXISTS idx_read_submission_attempt ON read_submission (attempt_id);
CREATE INDEX IF NOT EXISTS idx_read_submission_finalised_attempt ON read_submission (finalised_attempt_id);

-- ==========================================
-- Broker Attempt table
-- ==========================================

CREATE TABLE submission_attempt (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organism_key TEXT REFERENCES organism(grouping_key),
    campaign_label TEXT,
    status TEXT NOT NULL DEFAULT 'processing',
    lock_acquired_at TIMESTAMP NOT NULL DEFAULT NOW(),
    lock_expires_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ==========================================
-- Submission events (append-only audit trail)
-- ==========================================

CREATE TABLE submission_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attempt_id UUID NOT NULL REFERENCES submission_attempt(id) ON DELETE CASCADE,
    entity_type entity_type NOT NULL,
    submission_id UUID NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('claimed','accepted','rejected','released','expired','progress')),
    accession TEXT,
    details JSONB,
    at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_submission_event_attempt ON submission_event (attempt_id);
CREATE INDEX IF NOT EXISTS idx_submission_event_entity ON submission_event (entity_type, submission_id);

-- ==========================================
-- Assembly tables
-- ==========================================

-- Main assembly table
CREATE TABLE assembly (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organism_key TEXT REFERENCES organism(grouping_key) NOT NULL,
    sample_id UUID REFERENCES sample(id) NOT NULL,
    project_id UUID REFERENCES project(id),
    -- metadata fields for manifest file
    assembly_name TEXT NOT NULL,
    assembly_type text NOT NULL default 'clone or isolate',
    coverage float NOT NULL,
    program TEXT NOT NULL,
    mingaplength float,
    moleculetype molecule_type NOT NULL DEFAULT 'genomic DNA',
    fasta TEXT NOT NULL,

    version TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Assembly submission table
-- TO DO verify the types of files and any other fields we will save as outputs from the assembly pipelines
CREATE TABLE assembly_output_file (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assembly_id UUID REFERENCES assembly(id),
    type assembly_output_file_type NOT NULL,
    file_name TEXT NOT NULL,
    file_location TEXT NOT NULL,
    file_size BIGINT,
    file_checksum TEXT,
    file_format TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);


-- Assembly submission table
CREATE TABLE assembly_submission (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assembly_id UUID NOT NULL REFERENCES assembly(id) ON DELETE CASCADE,
    assembly_name TEXT NOT NULL, -- Do we need this for versioning?
    authority authority_type NOT NULL DEFAULT 'ENA',
    accession TEXT,
    organism_key TEXT REFERENCES organism(grouping_key) NOT NULL,
    sample_id UUID NOT NULL REFERENCES sample(id),

    internal_json JSONB,
    prepared_payload JSONB,
    returned_payload JSONB,
    -- The above are in .txt format, TO DO decide how to store these
    status submission_status NOT NULL DEFAULT 'draft',
    submitted_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE assembly_read (
    assembly_id UUID NOT NULL REFERENCES assembly(id),
    read_id UUID NOT NULL REFERENCES read(id),
    PRIMARY KEY (assembly_id, read_id)
);

-- ==========================================
-- Genome note tables
-- ==========================================

-- Main genome_note table
CREATE TABLE genome_note (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    genome_note_assembly_id UUID REFERENCES assembly(id) UNIQUE,
    organism_key TEXT REFERENCES organism(grouping_key) NOT NULL,
    -- Unique constraint on (is_published = TRUE, organism_key) to ensure only one published note per organism
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    title TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_genome_note_one_published_per_organism
ON genome_note (organism_key)
WHERE is_published = TRUE;

-- Genome note assembly table
CREATE TABLE genome_note_assembly (
    genome_note_id UUID NOT NULL REFERENCES genome_note(id),
    assembly_id UUID NOT NULL REFERENCES assembly(id),
    PRIMARY KEY (genome_note_id, assembly_id)
);

-- ==========================================
-- BPA initiative table
-- ==========================================

CREATE TABLE bpa_initiative (
    project_code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for common query patterns
CREATE INDEX idx_tax_id ON organism(tax_id);
CREATE INDEX idx_sample_organism_key ON sample(organism_key);
CREATE INDEX idx_experiment_sample_id ON experiment(sample_id);
CREATE INDEX idx_assembly_sample_id ON assembly(sample_id);
CREATE INDEX idx_assembly_organism_key ON assembly(organism_key);
