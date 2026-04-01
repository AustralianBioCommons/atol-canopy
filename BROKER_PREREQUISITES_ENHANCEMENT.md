# Broker Prerequisites Enhancement

## Problem
The broker API was returning null values for `prerequisites`, `validation_hints`, and `file_metadata` fields because:
1. Missing accession data in submission payloads
2. No way to distinguish between "not required" vs "required but not yet submitted"

## Solution
Enhanced the broker contract to include both **existing** and **required** accessions, allowing clients to understand dependency states.

### Key Architecture Understanding

**Crucial clarification**: Accessions are stored in different places:
- **Existing accessions**: Stored in database row fields (`project_accession`, `sample_accession`, etc.) and `accession_registry` table
- **prepared_payload**: Contains data for ENA submission, NOT existing accessions
- **Required accessions**: Specified in payload using `expected_*_accession` fields for dependencies not yet submitted

### Changes Made

#### 1. Extended BrokerPrerequisites Schema
```python
class BrokerPrerequisites(BaseModel):
    # Existing accessions (from database row fields)
    project_accession: Optional[str] = None
    sample_accession: Optional[str] = None
    experiment_accession: Optional[str] = None
    run_accession: Optional[str] = None
    study_accession: Optional[str] = None
    analysis_accession: Optional[str] = None

    # Required accessions (from payload, may not exist yet)
    required_project_accession: Optional[str] = None
    required_sample_accession: Optional[str] = None
    required_experiment_accession: Optional[str] = None
    required_run_accession: Optional[str] = None
    required_study_accession: Optional[str] = None
    required_analysis_accession: Optional[str] = None
```

#### 2. Enhanced Prerequisite Extraction Logic
- **Existing accessions**: Pulled from database row fields (`row.project_accession`, `row.sample_accession`, etc.)
- **Required accessions**: Extracted from payload when dependencies are required but missing
- Uses `expected_*_accession` fields in payloads for placeholders

#### 3. Updated Test Cases
- Tests now verify both existing and required accessions
- Demonstrates mixed states where some dependencies exist and others don't

### Usage Examples

#### Sample Submission with Existing Project Accession
**Database state**: `sample_submission.project_accession = "PRJ123456"`
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
    "project_accession": "PRJ123456",     // ✅ From database row
    "required_project_accession": null    // ✅ Already satisfied
  }
}
```

#### Experiment with Missing Study Accession
**Database state**: `experiment_submission.project_accession = null`
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
    "sample_accession": "SAMEA123456",     // ✅ From database row
    "study_accession": null,              // ❌ Missing from DB
    "required_study_accession": "PRJ123456"  // 📋 From payload
  }
}
```

#### Run with Missing Experiment Accession
**Database state**: `read_submission.experiment_accession = null`
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
    "experiment_accession": null,              // ❌ Missing from DB
    "required_experiment_accession": "ERX123456"  // 📋 From payload
  },
  "files": [
    {"filename": "reads.fastq.gz", "filetype": "fastq"}
  ]
}
```

### Data Flow Summary

1. **prepared_payload**: Contains ENA submission data (metadata, files, etc.)
2. **Database row fields**: Store actual accessions once submitted (`*_accession` fields)
3. **Payload expected fields**: Specify required but not-yet-submitted accessions (`expected_*_accession`)
4. **Broker response**: Combines both to show complete dependency state

### Client Benefits
1. **Clear dependency visibility**: See exactly what's missing vs what exists
2. **Submission planning**: Know what needs to be submitted first
3. **Progress tracking**: Distinguish between "not needed" vs "needed but not ready"
4. **Error prevention**: Avoid trying to submit entities with unmet dependencies

### Payload Fields for Required Accessions
- `expected_*_accession`: Placeholder for the accession that will be assigned
- `requires_*_accession`: Boolean flag indicating the dependency is required
- `requires_project_accession`: For samples
- `requires_study_accession`: For experiments

This enhancement maintains backward compatibility while providing much richer dependency information to broker clients, with the correct understanding of where different types of data are stored.
