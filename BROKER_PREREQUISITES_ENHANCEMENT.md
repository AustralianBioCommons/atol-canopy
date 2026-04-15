# Broker Prerequisites Enhancement

## Problem
The broker API was returning null values for `prerequisites`, `validation_hints`, and `file_metadata` fields because:
1. Missing accession data in submission payloads
2. No way to distinguish between "not required" vs "required but not yet submitted"

## Solution
Enhanced the broker contract to include **existing** accessions (resolved from `accession_registry`), allowing clients to decide whether dependency state is complete enough to submit.

### Key Architecture Understanding

**Crucial clarification**: Accessions are stored in different places:
- **Existing accessions**: Stored in database row fields (`project_accession`, `sample_accession`, etc.) and `accession_registry` table
- **prepared_payload**: Contains data for ENA submission, NOT existing accessions
- **Required accessions**: Specified in payload using `expected_*_accession` fields for dependencies not yet submitted

### Changes Made

#### 1. BrokerPrerequisites Schema
```python
class BrokerPrerequisites(BaseModel):
    # Existing accessions (from database row fields)
    project_accession: Optional[str] = None
    sample_accession: Optional[str] = None
    experiment_accession: Optional[str] = None
    run_accession: Optional[str] = None
    study_accession: Optional[str] = None
    analysis_accession: Optional[str] = None
```

#### 2. Enhanced Prerequisite Extraction Logic
- **Existing accessions**: Looked up from `accession_registry` via FK relationships on submission tables

#### 3. Updated Test Cases
- Tests now verify both existing and required accessions
- Demonstrates mixed states where some dependencies exist and others don't

### Usage Examples

#### Sample Submission with Existing Project Accession
**Database state**: `accession_registry` contains a project accession for the sample's `project_id`
```json
{
  "alias": "sample-1",
  "requires_project_accession": true
}
```
Result:
```json
{
  "prerequisites": {
    "project_accession": "PRJ123456"     // ✅ Resolved from accession_registry
  }
}
```

#### Experiment with Missing Study Accession
**Database state**: `accession_registry` does not contain a project accession for the experiment's `project_id`
```json
{
  "alias": "experiment-1",
  "requires_study_accession": true,
  "expected_study_accession": "PRJ123456"  // Required but not submitted
}
```
Result:
```json
{
  "prerequisites": {
    "sample_accession": "SAMEA123456",     // ✅ Resolved from accession_registry
    "study_accession": null               // ❌ Missing from registry
  }
}
```

#### Run with Missing Experiment Accession
**Database state**: `accession_registry` does not contain an experiment accession for the run's `experiment_id`
```json
{
  "alias": "run-1",
  "file_name": "reads.fastq.gz",
  "file_format": "fastq",
  "expected_experiment_accession": "ERX123456"  // Required but not submitted
}
```
Result:
```json
{
  "prerequisites": {
    "experiment_accession": null               // ❌ Missing from registry
  },
  "files": [
    {"filename": "reads.fastq.gz", "filetype": "fastq"}
  ]
}
```

### Data Flow Summary

1. **prepared_payload**: Contains ENA submission data (metadata, files, etc.)
2. **Database row fields**: Store actual accessions once submitted (`*_accession` fields)
3. **Broker response**: Shows resolved accessions (or `null`), and clients decide completeness

### Client Benefits
1. **Clear dependency visibility**: See what exists vs what is missing
2. **Single source of truth**: Accessions resolved from `accession_registry`

### Payload Fields for Required Accessions
- `expected_*_accession`: Placeholder for the accession that will be assigned
- `requires_*_accession`: Boolean flag indicating the dependency is required
- `requires_project_accession`: For samples
- `requires_study_accession`: For experiments (maps to `required_project_accession` in broker prerequisites)

This enhancement maintains backward compatibility while providing much richer dependency information to broker clients, with the correct understanding of where different types of data are stored.
