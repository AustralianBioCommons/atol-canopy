-- PostgreSQL schema for biological metadata tracking system
-- Based on ER diagram and requirements

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create ENUM types
CREATE TYPE submission_status AS ENUM ('draft', 'ready', 'submitted', 'accepted', 'rejected', 'replaced');
CREATE TYPE authority_type AS ENUM ('ENA', 'NCBI', 'DDBJ');
CREATE TYPE molecule_type AS ENUM ('genomic DNA', 'genomic RNA');
CREATE TYPE assembly_output_file_type AS ENUM ('QC', 'Other'); -- TODO define more specific types as needed
CREATE TYPE entity_type AS ENUM ('organism', 'sample', 'experiment', 'read', 'assembly', 'bioproject');
CREATE TYPE bioproject_type AS ENUM ('organism', 'genomic_data', 'assembly');
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
    user_id UUID REFERENCES users(id) NOT NULL,
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
    entity_id BIGINT NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (authority, entity_type, entity_id),
    UNIQUE (authority, accession)
);

-- ==========================================
-- Sample tables
-- ==========================================

-- Main sample table
CREATE TABLE sample (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organism_key int REFERENCES organism(grouping_key) NOT NULL,
    bpa_sample_id TEXT UNIQUE NOT NULL,
    bpa_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Sample submission table
CREATE TABLE sample_submission (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sample_id UUID REFERENCES sample(id),
    authority authority_type NOT NULL DEFAULT 'ENA',
    status submittion_status NOT NULL DEFAULT 'draft',
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
    entity_type_const TEXT NOT NULL DEFAULT 'sample' CHECK (entity_type_const = 'sample'),

    CONSTRAINT fk_self_accession
    FOREIGN KEY (accession, authority, entity_type_const, sample_id)
    REFERENCES accession_registry (accession, authority, entity_type, entity_id)
    DEFERRABLE INITIALLY DEFERRED,

    UNIQUE (sample_id, authority) WHERE (status = 'accepted' AND accession IS NOT NULL),
    -- TODO uniqueness constraint above?
    -- TODO consider if we want to keep track of former submissions that have been replaced/modified
);
-- UNIQUE (sample_id, authority) WHERE status = 'accepted' AND accession IS NOT NULL

-- ==========================================
-- Experiment tables
-- ==========================================

-- Main experiment table
CREATE TABLE experiment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sample_id UUID REFERENCES sample(id) NOT NULL,
    bpa_package_id TEXT UNIQUE NOT NULL,
    -- bpa_dataset_id TEXT UNIQUE NOT NULL,
    bpa_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Experiment submission table
CREATE TABLE experiment_submission (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    experiment_id UUID REFERENCES experiment(id),
    authority authority_type NOT NULL DEFAULT 'ENA',
    status submission_status NOT NULL DEFAULT 'draft',

    sample_id UUID REFERENCES sample(id) NOT NULL, -- nullable if sample doesn't exst yet? or are we happy to have the constraint that a sample & project needs to exist before we create an experiment, probs
    bioproject_id UUID REFERENCES bioproject(id) NOT NULL,

    project_accession TEXT,
    sample_accession TEXT,

    prepared_payload JSONB,
    response_payload JSONB,

    accession TEXT,

    -- constant to help the composite FK
  entity_type_const TEXT NOT NULL DEFAULT 'experiment' CHECK (entity_type_const = 'experiment'),

    submitted_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

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

    UNIQUE (experiment_id, authority) WHERE (status = 'accepted' AND accession IS NOT NULL),
     -- TODO consider if we want to keep track of former submissions that have been replaced/modified

);

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
    experiment_id UUID REFERENCES experiment(id) NOT NULL,
    bpa_resource_id TEXT UNIQUE NOT NULL,
    bpa_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE read_submission (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    read_id UUID REFERENCES read(id) NOT NULL,
    authority authority_type NOT NULL DEFAULT 'ENA',
    status submission_status NOT NULL DEFAULT 'draft',

    prepared_payload JSONB NOT NULL,
    response_payload JSONB,

    experiment_id UUID REFERENCES experiment(id) NOT NULL,
    project_id UUID REFERENCES project(id) NOT NULL,

    experiment_accession TEXT,

    accession TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- constant to help the composite FK
    entity_type_const TEXT NOT NULL DEFAULT 'read' CHECK (entity_type_const = 'read'),

    -- When accession is present, it must exist in the registry AND map to this same experiment:
  CONSTRAINT fk_self_accession
    FOREIGN KEY (accession, authority, entity_type_const, read_id)
    REFERENCES accession_registry (accession, authority, entity_type, entity_id)
    DEFERRABLE INITIALLY DEFERRED,

  -- Upstream accessions also validated (drafts allowed to be NULL):
  CONSTRAINT fk_exp_acc
    FOREIGN KEY (experiment_accession, authority)
    REFERENCES accession_registry (accession, authority)

    UNIQUE (read_id, authority) WHERE (status = 'accepted' AND accession IS NOT NULL),
);


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
    program varchar(255) NOT NULL,
    mingaplength float,
    moleculetype molecule_type NOT NULL DEFAULT 'genomic DNA',
    fasta varchar(255) NOT NULL,
    -- table to track many-to-many relationship between assembly and read
    assembly_read_id UUID REFERENCES assembly_read(id),

    version varchar(255) NOT NULL,
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
    assembly_id UUID REFERENCES assembly(id),
    assembly_name TEXT NOT NULL, -- Do we need this for versioning?
    authority authority_type NOT NULL DEFAULT 'ENA',
    accession TEXT,
    organism_key TEXT REFERENCES organism(grouping_key) NOT NULL,
    sample_id UUID REFERENCES sample(id) NOT NULL,

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
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assembly_id UUID REFERENCES assembly(id) NOT NULL,
    read_id UUID REFERENCES read(id) NOT NULL,
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
    genome_note_id UUID REFERENCES genome_note(id) NOT NULL,
    assembly_id UUID REFERENCES assembly(id) NOT NULL,
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

-- ==========================================
-- Bioproject tables
-- ==========================================

-- Main bioproject table
CREATE TABLE bioproject (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_type project_type NOT NULL,
    bioproject_accession TEXT UNIQUE,
    study_type TEXT NOT NULL,
    alias TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    centre_name TEXT,
    study_attributes JSONB,
    submitted_at TIMESTAMP,
    status submission_status NOT NULL DEFAULT 'draft',
    authority authority_type NOT NULL DEFAULT 'ENA',
    -- TODO consider if we want to track status of bioproject submission
    -- TODO confirm if we want study attributes, and enforece schema for json (or include as seperate table)
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Bioproject experiment table
CREATE TABLE bioproject_experiment (
    bioproject_id UUID REFERENCES bioproject(id) NOT NULL,
    experiment_id UUID REFERENCES experiment(id) NOT NULL,
    PRIMARY KEY (bioproject_id, experiment_id)
);


-- Create indexes for common query patterns
CREATE INDEX idx_organism_id ON organism(id);
CREATE INDEX idx_sample_organism_id ON sample(organism_id);
CREATE INDEX idx_experiment_sample_id ON experiment(sample_id);
CREATE INDEX idx_assembly_sample_id ON assembly(sample_id);
CREATE INDEX idx_assembly_organism_id ON assembly(organism_id);
CREATE INDEX idx_assembly_experiment_id ON assembly(experiment_id);
