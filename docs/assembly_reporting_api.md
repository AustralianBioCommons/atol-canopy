# Assembly Reporting API

This document describes how to use the assembly API to register a new assembly, then report pipeline results back to the database.

The flow has five stages:

1. **Create an assembly intent** — registers the assembly and returns a manifest
2. **Register a pipeline run** — links a GitHub repo + commit to the assembly
3. **Report QC reads** — after the QC stage completes, report the processed read files back to the database
4. **Report stage results** — one POST per completed (or failed) pipeline stage
5. **Query results** — retrieve all runs and their stage results

## Authentication

All endpoints require authentication.

- Most assembly write operations (`POST`, `PATCH`) require the `assemblies:write` policy.
- QC read reporting requires the `qc_reads:report` policy.

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/assemblies/intent/{taxon_id}` | Create an assembly and generate its manifest |
| `GET` | `/api/v1/assemblies/manifest/{taxon_id}` | Re-fetch the manifest for an existing assembly |
| `POST` | `/api/v1/assemblies/{assembly_id}/runs` | Register a pipeline invocation |
| `GET` | `/api/v1/assemblies/{assembly_id}/runs` | List all pipeline runs for an assembly |
| `POST` | `/api/v1/assemblies/{assembly_id}/qc-reads/report` | Report QC read files after the QC stage completes |
| `POST` | `/api/v1/assemblies/{assembly_id}/runs/{run_id}/stage-runs` | Report a stage result |
| `GET` | `/api/v1/assemblies/{assembly_id}/runs/{run_id}/stage-runs` | List stage results for a run |
| `PATCH` | `/api/v1/assemblies/{assembly_id}/runs/{run_id}/stage-runs/{stage_run_id}` | Update an existing stage result |

---

## Step 1 — Create an assembly intent

Call this endpoint once to register a new assembly. The server validates the supplied specimen samples, resolves all associated sequencing reads, generates a manifest JSON, and creates an `Assembly` record.

**Endpoint:** `POST /api/v1/assemblies/intent/{taxon_id}`

**Request body:**

```json
{
  "long_read_specimen_sample_id": "<uuid>",
  "hic_specimen_sample_ids": ["<uuid>"],
  "tol_id": "xgTaxSpecies1"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `long_read_specimen_sample_id` | Yes | Specimen sample used for PacBio or ONT long reads |
| `hic_specimen_sample_ids` | No | Specimen samples used for Hi-C reads |
| `tol_id` | No | Tree of Life identifier |

**Response:**

```json
{
  "assembly_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "version": 1,
  "manifest": { ... }
}
```

Save the `assembly_id` — it is required for all subsequent calls.

### Re-fetching the manifest

If the pipeline needs to retrieve the manifest at a later point rather than storing it from the intent response, use:

**Endpoint:** `GET /api/v1/assemblies/manifest/{taxon_id}`

An optional `?version=` query parameter can be used to retrieve a specific assembly version. Without it, the most recently created assembly is returned.

---

## Step 2 — Register a pipeline run

Before reporting any stage results, register the pipeline invocation. This creates an `assembly_run` linked to the assembly and records the specific GitHub repository and commit for that invocation. All stage results reported in Step 4 are scoped under this run.

**Endpoint:** `POST /api/v1/assemblies/{assembly_id}/runs`

**Request body:**

```json
{
  "github_repo": "https://github.com/your-org/assembly-pipeline",
  "git_commit": "abc123def456"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `github_repo` | Yes | URL of the GitHub repository containing the pipeline code |
| `git_commit` | Yes | Full commit SHA of the exact pipeline version that was run |

**Response:**

```json
{
  "id": "a1b2c3d4-...",
  "assembly_id": "f47ac10b-...",
  "github_repo": "https://github.com/your-org/assembly-pipeline",
  "git_commit": "abc123def456",
  "created_at": "2026-05-28T10:00:00Z",
  "updated_at": "2026-05-28T10:00:00Z",
  "stage_runs": []
}
```

Save the `id` from the response as `run_id` — it is required for Steps 4 and 5.

`run_id` is the parent key for all stage-run records. The stage-run routes still include `assembly_id`, but that is used to verify that the referenced `run_id` belongs to the expected assembly.

> **Re-runs:** If the same assembly is run again at a different commit (or from a different repo), simply call this endpoint again. Each invocation gets its own `run_id`, and the two runs are distinguished by their `github_repo` + `git_commit` combination.

---

## Step 3 — Report QC reads

After the QC stage completes, the pipeline must report the processed read files back to the database. This is a separate call from reporting the stage result (Step 4) and uses a different endpoint.

This endpoint records the QC metrics and output files against a specific assembly. Each call creates one `qc_read` record linked to:

- the source experiment
- the target assembly
- one or two source read MD5 sums listed in `source_read_file_checksums`

The reported files must be either a single-file read set (for example one CRAM or one single-end FASTQ) or a paired FASTQ set (one R1 and one R2).

Unlike stage results, QC read reports are linked directly to `assembly_id`; they are not nested under `run_id`.

**Endpoint:** `POST /api/v1/assemblies/{assembly_id}/qc-reads/report`

> Requires the `qc_reads:report` policy.

**Request body:**

```json
{
  "bpa_package_id": "pkg-001",
  "source_read_file_checksums": [
    "d41d8cd98f00b204e9800998ecf8427e",
    "0cc175b9c0f1b6a831c399e269772661"
  ],
  "base_count": 15000000000,
  "read_count": 5000000,
  "qc_bases_removed": 120000,
  "qc_reads_removed": 400,
  "mean_gc_content": 42.3,
  "n50_length": 18500,
  "checksums": {
    "qc/sample_R1.fastq.gz": {
      "md5": "d41d8cd98f00b204e9800998ecf8427e",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    },
    "qc/sample_R2.fastq.gz": {
      "md5": "0cc175b9c0f1b6a831c399e269772661",
      "sha256": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"
    }
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `bpa_package_id` | Yes | BPA package ID for the experiment this QC result belongs to |
| `source_read_file_checksums` | Yes | One or two source read file checksums used to produce this QC result |
| `base_count` | Yes | Total number of bases after QC |
| `read_count` | Yes | Total number of reads after QC |
| `qc_bases_removed` | Yes | Number of bases removed during QC |
| `qc_reads_removed` | Yes | Number of reads removed during QC |
| `mean_gc_content` | Yes | Mean GC content (percentage) |
| `n50_length` | No | N50 read length |
| `checksums` | Yes | Map of reported filenames to their MD5 and SHA-256 checksums |

Each `checksums` entry:

| Field | Required | Description |
|-------|----------|-------------|
| object key | Yes | The reported filename or path |
| `md5` | Yes | MD5 checksum (32 lowercase hex characters) |
| `sha256` | Yes | SHA-256 checksum (64 lowercase hex characters) |

Validation rules:

- `bpa_package_id` must identify an existing experiment
- the resolved experiment must belong to the target assembly specimen lineage
- the resolved experiment must be present in the target assembly manifest inputs
- `source_read_file_checksums` must contain one or two unique MD5 sums
- every submitted source MD5 sum must match a `read.file_checksum` belonging to the resolved experiment
- One checksum entry: accepted for a single-file read set when the filename ends in `.cram`, `.fastq`, `.fastq.gz`, `.fq`, or `.fq.gz`
- Two checksum entries: accepted for paired FASTQ when the filenames identify one R1/read1 file and one R2/read2 file
- More than two files are rejected by this endpoint

Once this call succeeds, the QC stage result should then be reported as a stage run (Step 4) in the same way as any other stage.

---

## Step 4 — Report stage results

Call this endpoint once for each successful pipeline stage result within a specific pipeline invocation.

**Endpoint:** `POST /api/v1/assemblies/{assembly_id}/runs/{run_id}/stage-runs`

The created record belongs to `run_id` (`assembly_run`), not directly to `assembly_id`.

**Request body:**

```json
{
  "stage_name": "genomeassembly",
  "data": {
    "n50": 15000,
    "num_contigs": 42
  },
  "started_at": "2026-05-28T10:00:00Z",
  "completed_at": "2026-05-28T14:30:00Z",
  "files": [
    {
      "storage_type": "s3",
      "endpoint": "https://projects.pawsey.org.au",
      "location_root": "your-bucket",
      "location_path": "path/to/assembly.fasta",
      "sha256sum": "abc123..."
    }
  ]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `stage_name` | Yes | Name of the pipeline stage (see [Known stages](#known-stages)) |
| `data` | No | Arbitrary key/value result data for this stage (e.g. N50, contig counts) |
| `started_at` | No | When the stage started (ISO 8601 with timezone) |
| `completed_at` | No | When the stage finished (ISO 8601 with timezone) |
| `files` | No | Output files produced by this stage (see [Reporting files](#reporting-files)) |

### Known stages

| Stage name | Category | Description |
|------------|----------|-------------|
| `genomeassembly` | pipeline | Initial genome assembly |
| `ascc` | pipeline | Assembly contamination and quality checks |
| `treeval` | pipeline | Tree of Life validation |
| `curation-pretext` | pipeline | Pre-curation visualisation |
| `manual-curation` | manual | Manual curation step |

### Reporting files

Each entry in the `files` array describes one output file:

| Field | Required | Description |
|-------|----------|-------------|
| `storage_type` | Yes | Storage backend, e.g. `s3`, `gcs` |
| `endpoint` | Yes | Storage service endpoint, e.g. `https://projects.pawsey.org.au` |
| `location_root` | Yes | Top-level storage namespace, such as a bucket or filesystem root |
| `location_path` | Yes | Path/key within `location_root` |
| `sha256sum` | Yes | SHA-256 checksum of the file for integrity verification |

For the usual S3-compatible workflow used by this project:

- `location_root` = bucket
- `location_path` = remote path / object key within that bucket

Example:

```json
{
  "storage_type": "s3",
  "endpoint": "https://projects.pawsey.org.au",
  "location_root": "assembly-results",
  "location_path": "genomeassembly/assembly.fasta.gz",
  "sha256sum": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
}
```

### Updating a stage result

If a stage result needs to be corrected after submission, use the PATCH endpoint:

**Endpoint:** `PATCH /api/v1/assemblies/{assembly_id}/runs/{run_id}/stage-runs/{stage_run_id}`

All fields are optional. Only the fields provided will be updated.

```json
{
  "data": {
    "n50": 16000
  }
}
```

> **Note on files:** If `files` is included in a PATCH request, it **replaces** all existing files for that stage run. Re-include any files you want to keep.

---

## Step 5 — Query results

### List all runs for an assembly

Returns every pipeline invocation for the assembly, newest first. Each run includes its stage results nested inline.

**Endpoint:** `GET /api/v1/assemblies/{assembly_id}/runs`

**Response:**

```json
[
  {
    "id": "a1b2c3d4-...",
    "assembly_id": "f47ac10b-...",
    "github_repo": "https://github.com/your-org/assembly-pipeline",
    "git_commit": "abc123def456",
    "created_at": "2026-05-28T10:00:00Z",
    "updated_at": "2026-05-28T14:30:00Z",
    "stage_runs": [
      {
        "id": "b2c3d4e5-...",
        "assembly_run_id": "a1b2c3d4-...",
        "stage_name": "genomeassembly",
        "data": { "n50": 15000, "num_contigs": 42 },
        "started_at": "2026-05-28T10:00:00Z",
        "completed_at": "2026-05-28T14:30:00Z",
        "files": [ ... ]
      }
    ]
  }
]
```

### List stage results for a specific run

**Endpoint:** `GET /api/v1/assemblies/{assembly_id}/runs/{run_id}/stage-runs`

Returns the stage results for a single pipeline invocation, newest first. The `run_id` in the path identifies the parent `assembly_run`.

---

## Complete example

```
# 1. Create the assembly intent
POST /api/v1/assemblies/intent/9606
{
  "long_read_specimen_sample_id": "11111111-1111-1111-1111-111111111111",
  "hic_specimen_sample_ids": ["22222222-2222-2222-2222-222222222222"],
  "tol_id": "xgHomoSapiens1"
}
→ { "assembly_id": "f47ac10b-...", "version": 1, "manifest": { ... } }

# 2. Register the pipeline invocation
POST /api/v1/assemblies/f47ac10b-.../runs
{
  "github_repo": "https://github.com/org/pipeline",
  "git_commit": "abc123def4567890abc123def4567890abc123de"
}
→ { "id": "a1b2c3d4-..." }

# 3. QC stage completes — report QC reads, then report the stage result
POST /api/v1/assemblies/f47ac10b-.../qc-reads/report
{
  "bpa_package_id": "pkg-001",
  "source_read_file_checksums": [
    "d41d8cd98f00b204e9800998ecf8427e",
    "0cc175b9c0f1b6a831c399e269772661"
  ],
  "base_count": 15000000000,
  "read_count": 5000000,
  "qc_bases_removed": 120000,
  "qc_reads_removed": 400,
  "mean_gc_content": 42.3,
  "n50_length": 18500,
  "checksums": {
    "qc/sample_R1.fastq.gz": {
      "md5": "d41d8cd98f00b204e9800998ecf8427e",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    },
    "qc/sample_R2.fastq.gz": {
      "md5": "0cc175b9c0f1b6a831c399e269772661",
      "sha256": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"
    }
  }
}

POST /api/v1/assemblies/f47ac10b-.../runs/a1b2c3d4-.../stage-runs
{
  "stage_name": "ascc",
  "data": {
    "contamination_score": 0.02,
    "adapter_content_pct": 0.1
  },
  "started_at": "2026-05-28T10:00:00Z",
  "completed_at": "2026-05-28T11:15:00Z",
  "files": [
    {
      "storage_type": "s3",
      "endpoint": "https://projects.pawsey.org.au",
      "location_root": "assembly-results",
      "location_path": "ascc/report.html",
      "sha256sum": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  ]
}

# 4. Report remaining stage results as each completes
POST /api/v1/assemblies/f47ac10b-.../runs/a1b2c3d4-.../stage-runs
{
  "stage_name": "genomeassembly",
  "data": {
    "n50": 15000000,
    "num_contigs": 42
  },
  "started_at": "2026-05-28T11:30:00Z",
  "completed_at": "2026-05-28T14:30:00Z",
  "files": [
    {
      "storage_type": "s3",
      "endpoint": "https://projects.pawsey.org.au",
      "location_root": "assembly-results",
      "location_path": "genomeassembly/assembly.fasta.gz",
      "sha256sum": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    }
  ]
}

POST /api/v1/assemblies/f47ac10b-.../runs/a1b2c3d4-.../stage-runs
{
  "stage_name": "treeval",
  "data": {
    "pass": true,
    "warnings": 0
  },
  "started_at": "2026-05-28T15:00:00Z",
  "completed_at": "2026-05-28T16:00:00Z",
  "files": [
    {
      "storage_type": "s3",
      "endpoint": "https://projects.pawsey.org.au",
      "location_root": "assembly-results",
      "location_path": "treeval/summary.json",
      "sha256sum": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    }
  ]
}

# 5. Query all results
GET /api/v1/assemblies/f47ac10b-.../runs
→ [ { "github_repo": "...", "git_commit": "abc123", "stage_runs": [ ... ] } ]
```
