-- PostgreSQL schema for biological metadata tracking system
-- Based on ER diagram and requirements
-- NOTE: This file is kept in sync with the database after each migration
-- Regenerate with: docker compose exec db pg_dump -U <user> -d <dbname> --schema-only --no-owner --no-acl

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create ENUM types
CREATE TYPE submission_status AS ENUM ('draft', 'ready', 'submitting', 'rejected', 'accepted', 'replaced');
CREATE TYPE authority_type AS ENUM ('ENA', 'NCBI', 'DDBJ');
CREATE TYPE molecule_type AS ENUM ('genomic DNA', 'genomic RNA');
CREATE TYPE assembly_data_types AS ENUM (
    'PACBIO_SMRT',
    'PACBIO_SMRT_HIC',
    'OXFORD_NANOPORE',
    'OXFORD_NANOPORE_HIC',
    'PACBIO_SMRT_OXFORD_NANOPORE',
    'PACBIO_SMRT_OXFORD_NANOPORE_HIC'
);
CREATE TYPE assembly_file_type AS ENUM (
    'FASTA',
    'QC_REPORT',
    'STATISTICS',
    'OTHER'
);
CREATE TYPE entity_type AS ENUM ('organism', 'sample', 'experiment', 'read', 'assembly', 'project', 'qc_read');
CREATE TYPE project_type AS ENUM ('root', 'genomic_data', 'assembly');
CREATE TYPE sample_kind AS ENUM ('specimen', 'derived');
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ==========================================
-- Authentication refresh tokens table
-- ==========================================

CREATE TABLE refresh_token (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token_hash TEXT NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ==========================================
-- Organism tables
-- ==========================================

-- Main organism table
CREATE TABLE organism (
    taxon_id int PRIMARY KEY,
    -- We need to check that the scientific name = the tax id level, because we have a bunch of tax_ids that are the same for organisms which should have a more granular taxid level
    scientific_name TEXT,
    genus TEXT,
    species TEXT,
    common_name TEXT,
    common_name_source TEXT,
    -- TODO check common name is coming through from mapper, and set common_name_source
    -- family TEXT,
    -- order_or_group TEXT,
    -- class TEXT,
    -- phylum TEXT,
    infraspecific_epithet TEXT,
    culture_or_strain_id TEXT,
    authority TEXT,
    atol_scientific_name TEXT,
    tax_string TEXT,
    ncbi_order TEXT,
    ncbi_family TEXT,
    busco_dataset_name TEXT,
    bpa_json JSONB,
    taxonomy_lineage_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ==========================================
-- Taxonomy info table (1:1 extension of organism)
-- ==========================================

CREATE TABLE taxonomy_info (
    taxon_id INT PRIMARY KEY REFERENCES organism(taxon_id) ON DELETE CASCADE,
    busco_odb10_dataset_name TEXT,
    busco_odb12_dataset_name TEXT,
    find_plastid BOOLEAN,
    hic_motif TEXT,
    mitochondrial_genetic_code_id INTEGER,
    mitohifi_reference_species TEXT,
    oatk_hmm_name TEXT,
    defined_class TEXT,
    augustus_dataset_name TEXT,
    genetic_code_id INTEGER
);

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
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
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
    taxon_id INT NOT NULL REFERENCES organism(taxon_id) ON DELETE CASCADE,
    project_type project_type NOT NULL,
    project_accession TEXT UNIQUE,
    study_type TEXT NOT NULL,
    alias TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    centre_name TEXT,
    study_attributes JSONB,
    -- TODO remove submitted_at, should only be for submission table
    submitted_at TIMESTAMPTZ,
    status submission_status NOT NULL DEFAULT 'draft',
    authority authority_type NOT NULL DEFAULT 'ENA',
    -- TODO confirm if we want study attributes, and enforece schema for json (or include as seperate table)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_one_project_type_per_organism
  ON project (taxon_id, project_type);

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

    submitted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- attempt linkage
    attempt_id UUID,
    finalised_attempt_id UUID,

    -- broker lease/claim fields (attempt-scoped)
    lock_acquired_at TIMESTAMPTZ,
    lock_expires_at TIMESTAMPTZ,

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
CREATE INDEX IF NOT EXISTS idx_project_submission_status ON project_submission (status);
CREATE INDEX IF NOT EXISTS idx_project_submission_lock_expires_at ON project_submission (lock_expires_at);

-- ==========================================
-- Sample tables
-- ==========================================

-- Main sample table
CREATE TABLE sample (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    taxon_id INT NOT NULL REFERENCES organism(taxon_id) ON DELETE CASCADE,
    bpa_sample_id TEXT,
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
    collected_by TEXT NOT NULL,
    collecting_institution TEXT NOT NULL,
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

    derived_from_sample_id UUID REFERENCES sample(id) ON DELETE CASCADE,
    kind sample_kind NOT NULL,

  CONSTRAINT derived_from_sample_id_matches_kind CHECK (
    (kind = 'specimen' AND derived_from_sample_id IS NULL)
    OR
    (kind = 'derived'  AND derived_from_sample_id IS NOT NULL)
  ),
  CONSTRAINT chk_sample_latitude CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
  CONSTRAINT chk_sample_longitude CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    extensions JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
    submitted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- constant to help the composite FK
    entity_type_const entity_type NOT NULL DEFAULT 'sample' CHECK (entity_type_const = 'sample'),

    -- prerequisite FK (for normalized accession lookups)
    -- TODO remove: samples are not project-scoped; project context (if any) is derived via experiments
    project_id UUID NOT NULL REFERENCES project(id),

    -- attempt linkage
    attempt_id UUID,
    finalised_attempt_id UUID,

    -- broker lease/claim fields (attempt-scoped)
    lock_acquired_at TIMESTAMPTZ,
    lock_expires_at TIMESTAMPTZ,

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
CREATE INDEX IF NOT EXISTS idx_sample_submission_status ON sample_submission (status);
CREATE INDEX IF NOT EXISTS idx_sample_submission_lock_expires_at ON sample_submission (lock_expires_at);
CREATE INDEX IF NOT EXISTS idx_sample_submission_project_id ON sample_submission (project_id);

-- Support parent/child lookups for derived samples
CREATE INDEX IF NOT EXISTS idx_sample_derived_from_sample_id ON sample(derived_from_sample_id);

-- Enforce uniqueness: one specimen sample per (taxon_id, specimen_id)
CREATE UNIQUE INDEX IF NOT EXISTS uq_specimen_per_organism_specimen_id
  ON sample (taxon_id, specimen_id)
  WHERE kind = 'specimen' AND specimen_id IS NOT NULL;

-- Enforce uniqueness: bpa_sample_id must be unique for derived samples
CREATE UNIQUE INDEX IF NOT EXISTS uq_derived_bpa_sample_id
  ON sample (bpa_sample_id)
  WHERE kind = 'derived' AND bpa_sample_id IS NOT NULL;

-- Index for efficient lookup by taxon_id + specimen_id
CREATE INDEX IF NOT EXISTS idx_sample_organism_specimen_lookup
  ON sample (taxon_id, specimen_id)
  WHERE specimen_id IS NOT NULL;

-- UNIQUE (sample_id, authority) WHERE status = 'accepted' AND accession IS NOT NULL

-- ==========================================
-- Experiment tables
-- ==========================================

-- Main experiment table
CREATE TABLE experiment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sample_id UUID NOT NULL REFERENCES sample(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    bpa_package_id TEXT UNIQUE NOT NULL,
    bioplatforms_base_url TEXT,
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
    extensions JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Experiment submission table
CREATE TABLE experiment_submission (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    experiment_id UUID NOT NULL REFERENCES experiment(id) ON DELETE CASCADE,
    authority authority_type NOT NULL DEFAULT 'ENA',
    status submission_status NOT NULL DEFAULT 'draft',

    project_accession TEXT,
    sample_accession TEXT,
    prepared_payload JSONB,
    response_payload JSONB,

    accession TEXT,

    -- constant to help the composite FK
    entity_type_const entity_type NOT NULL DEFAULT 'experiment' CHECK (entity_type_const = 'experiment'),

    submitted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    attempt_id UUID,
    finalised_attempt_id UUID,

    -- broker lease/claim fields
    lock_acquired_at TIMESTAMPTZ,
    lock_expires_at TIMESTAMPTZ,

      -- When accession is present, it must exist in the registry AND map to this same experiment:
  CONSTRAINT fk_self_accession
    FOREIGN KEY (accession, authority, entity_type_const, experiment_id)
    REFERENCES accession_registry (accession, authority, entity_type, entity_id)
    DEFERRABLE INITIALLY DEFERRED
);

-- Broker lease/claim index
CREATE INDEX IF NOT EXISTS idx_experiment_submission_attempt ON experiment_submission (attempt_id);
CREATE INDEX IF NOT EXISTS idx_experiment_submission_finalised_attempt ON experiment_submission (finalised_attempt_id);
CREATE INDEX IF NOT EXISTS idx_experiment_submission_status ON experiment_submission (status);
CREATE INDEX IF NOT EXISTS idx_experiment_submission_lock_expires_at ON experiment_submission (lock_expires_at);

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
    extensions JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ==========================================
-- Broker Attempt table
-- ==========================================

CREATE TABLE submission_attempt (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    taxon_id INT REFERENCES organism(taxon_id),
    campaign_label TEXT,
    -- TODO make ENUM
    status TEXT NOT NULL DEFAULT 'processing',
    lock_acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lock_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_submission_attempt_status ON submission_attempt (status);
CREATE INDEX IF NOT EXISTS idx_submission_attempt_lock_expires_at ON submission_attempt (lock_expires_at);

-- ==========================================
-- Submission events (append-only audit trail)
-- ==========================================
-- Note: Each submission creates multiple rows (claimed -> released/accepted/rejected)
-- This provides full audit history but means ~2x rows per submission.
-- TODO: If table size becomes an issue, consider switching to single-row-per-submission
-- with UPDATE instead of INSERT for state transitions.

CREATE TABLE submission_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attempt_id UUID NOT NULL REFERENCES submission_attempt(id) ON DELETE CASCADE,
    entity_type entity_type NOT NULL,
    submission_id UUID NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('claimed','accepted','rejected','released','expired','progress')),
    accession TEXT,
    details JSONB,
    at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_submission_event_attempt ON submission_event (attempt_id);
CREATE INDEX IF NOT EXISTS idx_submission_event_entity ON submission_event (entity_type, submission_id);

-- ==========================================
-- Assembly tables
-- ==========================================

-- Main assembly table
CREATE TABLE assembly (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    taxon_id INT REFERENCES organism(taxon_id) NOT NULL,
    sample_id UUID REFERENCES sample(id) NOT NULL,
    project_id UUID REFERENCES project(id),

    -- Assembly metadata
    assembly_name TEXT,
    assembly_type TEXT NOT NULL DEFAULT 'clone or isolate',
    tol_id TEXT,
    data_types assembly_data_types NOT NULL,
    coverage FLOAT,
    program TEXT,
    mingaplength FLOAT,
    moleculetype molecule_type NOT NULL DEFAULT 'genomic DNA',
    description TEXT,

    -- Intent-flow specimen samples
    -- long_read_specimen_sample_id: the specimen sample supplying PacBio / ONT reads
    -- hic_specimen_sample_id: the specimen sample supplying Hi-C reads (optional)
    long_read_specimen_sample_id UUID REFERENCES sample(id),
    hic_specimen_sample_id UUID REFERENCES sample(id),

    -- Persisted manifest generated at intent time
    manifest_json JSONB,

    -- Version is scoped by (taxon_id, long_read_specimen_sample_id) for intent-flow assemblies
    version INTEGER NOT NULL DEFAULT 1,

    -- Assembly lifecycle status
    status TEXT NOT NULL DEFAULT 'requested',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_assembly_status CHECK (
        status IN ('requested', 'running', 'curating', 'completed', 'failed', 'cancelled')
    )
);

CREATE TABLE assembly_run (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    taxon_id INT REFERENCES organism(taxon_id) NOT NULL,
    sample_id UUID REFERENCES sample(id) NOT NULL,
    data_types assembly_data_types NOT NULL,
    version INTEGER NOT NULL,
    tol_id TEXT,
    status TEXT NOT NULL DEFAULT 'reserved',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE assembly_file (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assembly_id UUID REFERENCES assembly(id) ON DELETE CASCADE NOT NULL,
    file_type assembly_file_type NOT NULL,
    file_name TEXT NOT NULL,
    file_location TEXT NOT NULL,
    file_size BIGINT,
    file_checksum TEXT,
    file_checksum_method TEXT DEFAULT 'MD5',
    file_format TEXT,
    description TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_assembly_file_assembly_id ON assembly_file(assembly_id);
CREATE INDEX idx_assembly_file_type ON assembly_file(assembly_id, file_type);

-- Index for legacy version lookups (generic create flow)
CREATE INDEX idx_assembly_version_key ON assembly(data_types, taxon_id, sample_id, version);

-- Index for intent-flow version lookups (scoped by taxon + long-read specimen sample)
CREATE INDEX idx_assembly_intent_version_key ON assembly(taxon_id, long_read_specimen_sample_id);


-- Assembly submission table (simplified - no broker integration)
CREATE TABLE assembly_submission (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assembly_id UUID NOT NULL REFERENCES assembly(id) ON DELETE CASCADE,
    authority authority_type NOT NULL DEFAULT 'ENA',
    status submission_status NOT NULL DEFAULT 'draft',

    -- ENA accessions
    accession TEXT,
    sample_accession TEXT,
    project_accession TEXT,

    -- Submission payloads
    manifest_json JSONB,
    response_payload JSONB,

    -- Metadata
    submitted_at TIMESTAMPTZ,
    submitted_by UUID REFERENCES users(id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Only one accepted submission per assembly+authority
CREATE UNIQUE INDEX uq_assembly_one_accepted
  ON assembly_submission (assembly_id, authority)
  WHERE status = 'accepted' AND accession IS NOT NULL;

CREATE TABLE assembly_read (
    assembly_id UUID NOT NULL REFERENCES assembly(id),
    read_id UUID NOT NULL REFERENCES read(id),
    PRIMARY KEY (assembly_id, read_id)
);

-- ==========================================
-- Assembly stage catalog and reporting tables
-- ==========================================

CREATE TABLE assembly_stage (
    name TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_assembly_stage_category CHECK (category IN ('pipeline', 'manual'))
);

-- Seed rows
INSERT INTO assembly_stage (name, category) VALUES
    ('genomeassembly', 'pipeline'),
    ('ascc',           'pipeline'),
    ('treeval',        'pipeline'),
    ('curation-pretext', 'pipeline'),
    ('manual-curation',  'manual');

CREATE TABLE assembly_stage_run (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assembly_id UUID NOT NULL REFERENCES assembly(id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL REFERENCES assembly_stage(name),
    status TEXT NOT NULL,
    external_run_id TEXT,
    attempt INTEGER NOT NULL DEFAULT 1,
    stats JSONB NOT NULL DEFAULT '{}',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_assembly_stage_run_status CHECK (
        status IN ('running', 'succeeded', 'failed', 'cancelled')
    ),
    CONSTRAINT uq_stage_run_assembly_stage_attempt UNIQUE (assembly_id, stage_name, attempt)
);

CREATE INDEX ix_assembly_stage_run_assembly_id ON assembly_stage_run(assembly_id);

CREATE TABLE assembly_stage_run_file (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assembly_stage_run_id UUID NOT NULL REFERENCES assembly_stage_run(id) ON DELETE CASCADE,
    storage_type TEXT NOT NULL,
    storage_uri TEXT NOT NULL,
    storage_details JSONB NOT NULL DEFAULT '{}',
    sha256sum TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_assembly_stage_run_file_run_id ON assembly_stage_run_file(assembly_stage_run_id);

-- ==========================================
-- Genome note tables
-- ==========================================

-- Main genome_note table
-- Tracks versioned genome notes linked to assemblies
-- Each organism can have multiple draft versions but only one published version
CREATE TABLE genome_note (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    taxon_id INT NOT NULL REFERENCES organism(taxon_id) ON DELETE CASCADE,
    assembly_id UUID NOT NULL REFERENCES assembly(id) ON DELETE CASCADE,

    -- Versioning: auto-increment per organism
    version INTEGER NOT NULL,

    -- Content and metadata
    title TEXT NOT NULL,
    note_url TEXT NOT NULL,  -- URL hosting the genome note

    -- Publication status
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    published_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Ensure version uniqueness per organism
    UNIQUE (taxon_id, version)
);

-- Ensure only one published note per organism
CREATE UNIQUE INDEX uq_genome_note_one_published_per_organism
    ON genome_note (taxon_id)
    WHERE is_published = TRUE;

-- Indexes for efficient lookups
CREATE INDEX idx_genome_note_taxon_id ON genome_note(taxon_id);
CREATE INDEX idx_genome_note_assembly_id ON genome_note(assembly_id);
CREATE INDEX idx_genome_note_published ON genome_note(taxon_id, is_published)
    WHERE is_published = TRUE;

-- ==========================================
-- QC Read tables
-- ==========================================

CREATE TABLE qc_read (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    experiment_id UUID NOT NULL REFERENCES experiment(id) ON DELETE CASCADE,
    base_count BIGINT NOT NULL,
    read_count BIGINT NOT NULL,
    qc_bases_removed BIGINT NOT NULL,
    qc_reads_removed BIGINT NOT NULL,
    mean_gc_content FLOAT NOT NULL,
    n50_length BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE qc_read_file (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    qc_read_id UUID NOT NULL REFERENCES qc_read(id) ON DELETE CASCADE,
    file_type TEXT NOT NULL CHECK (file_type IN ('cram', 'fastq_r1', 'fastq_r2')),
    storage_backend TEXT NOT NULL,
    storage_profile TEXT NOT NULL,
    bucket_name TEXT NOT NULL,
    path_to_file TEXT NOT NULL,
    md5_checksum TEXT NOT NULL CHECK (md5_checksum ~ '^[a-f0-9]{32}$'),
    sha256_checksum TEXT NOT NULL CHECK (sha256_checksum ~ '^[a-f0-9]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE qc_read_submission (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    qc_read_id UUID NOT NULL REFERENCES qc_read(id) ON DELETE CASCADE,
    experiment_id UUID REFERENCES experiment(id) ON DELETE CASCADE,
    authority authority_type NOT NULL DEFAULT 'ENA',
    status submission_status NOT NULL DEFAULT 'draft',

    prepared_payload JSONB NOT NULL,
    response_payload JSONB,

    accession TEXT,

    -- constant to help the composite FK
    entity_type_const entity_type NOT NULL DEFAULT 'qc_read' CHECK (entity_type_const = 'qc_read'),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- attempt linkage
    attempt_id UUID,
    finalised_attempt_id UUID,

    -- broker lease/claim fields
    lock_acquired_at TIMESTAMPTZ,
    lock_expires_at TIMESTAMPTZ,

    CONSTRAINT fk_qc_read_submission_accession
        FOREIGN KEY (accession, authority, entity_type_const, qc_read_id)
        REFERENCES accession_registry (accession, authority, entity_type, entity_id)
        DEFERRABLE INITIALLY DEFERRED
);

-- QC read indexes
CREATE INDEX idx_qc_read_experiment_id ON qc_read(experiment_id);
CREATE INDEX idx_qc_read_file_qc_read_id ON qc_read_file(qc_read_id);
CREATE INDEX idx_qc_read_submission_attempt ON qc_read_submission (attempt_id);
CREATE INDEX idx_qc_read_submission_experiment_id ON qc_read_submission (experiment_id);
CREATE INDEX idx_qc_read_submission_finalised_attempt ON qc_read_submission (finalised_attempt_id);
CREATE INDEX idx_qc_read_submission_lock_expires_at ON qc_read_submission (lock_expires_at);
CREATE INDEX idx_qc_read_submission_status ON qc_read_submission (status);

CREATE UNIQUE INDEX uq_qc_read_one_accepted
  ON qc_read_submission (qc_read_id, authority)
  WHERE status = 'accepted' AND accession IS NOT NULL;

-- ==========================================
-- BPA initiative table
-- ==========================================

CREATE TABLE bpa_initiative (
    project_code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for common query patterns
CREATE INDEX idx_sample_taxon_id ON sample(taxon_id);
CREATE INDEX idx_experiment_sample_id ON experiment(sample_id);
CREATE INDEX idx_experiment_project_id ON experiment(project_id);
CREATE INDEX idx_assembly_sample_id ON assembly(sample_id);
CREATE INDEX idx_assembly_taxon_id ON assembly(taxon_id);
