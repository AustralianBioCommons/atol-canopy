# Broker Prerequisites Enhancement

## Problem
The broker API was returning null values for `prerequisites`, `validation_hints`, and `file_metadata` fields because:
1. Missing accession data in submission payloads
2. No way to distinguish between "not required" vs "required but not yet submitted"

## Solution
Enhanced the broker contract to include both **existing** and **required** accessions, allowing clients to understand dependency states.

### Changes Made

#### 1. Extended BrokerPrerequisites Schema
```python
class BrokerPrerequisites(BaseModel):
    # Existing accessions (already submitted and available)
    project_accession: Optional[str] = None
    sample_accession: Optional[str] = None
    experiment_accession: Optional[str] = None
    run_accession: Optional[str] = None
    study_accession: Optional[str] = None
    analysis_accession: Optional[str] = None
    
    # Required accessions (needed but may not exist yet)
    required_project_accession: Optional[str] = None
    required_sample_accession: Optional[str] = None
    required_experiment_accession: Optional[str] = None
    required_run_accession: Optional[str] = None
    required_study_accession: Optional[str] = None
    required_analysis_accession: Optional[str] = None
```

#### 2. Enhanced Prerequisite Extraction Logic
- **Existing accessions**: Pulled from database rows or payload (existing behavior)
- **Required accessions**: Extracted from payload when dependencies are required but missing
- Uses `expected_*_accession` fields in payloads for placeholders

#### 3. Updated Test Cases
- Tests now verify both existing and required accessions
- Demonstrates mixed states where some dependencies exist and others don't

### Usage Examples

#### Sample Submission
```json
{
  "alias": "sample-1",
  "project_accession": "PRJ123456",  // Existing
  "requires_project_accession": true
}
```
Result:
```json
{
  "prerequisites": {
    "project_accession": "PRJ123456",     // ✅ Exists
    "required_project_accession": null    // ✅ Already satisfied
  }
}
```

#### Experiment with Missing Dependencies
```json
{
  "alias": "experiment-1",
  "sample_accession": "SAMEA123456",     // Exists
  "requires_study_accession": true,
  "expected_study_accession": "PRJ123456"  // Required but not submitted
}
```
Result:
```json
{
  "prerequisites": {
    "sample_accession": "SAMEA123456",     // ✅ Exists
    "study_accession": null,              // ❌ Missing
    "required_study_accession": "PRJ123456"  // 📋 Required
  }
}
```

#### Run with Missing Experiment
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
    "experiment_accession": null,              // ❌ Missing
    "required_experiment_accession": "ERX123456"  // 📋 Required
  },
  "files": [
    {"filename": "reads.fastq.gz", "filetype": "fastq"}
  ]
}
```

### Client Benefits
1. **Clear dependency visibility**: Can see exactly what's missing
2. **Submission planning**: Know what needs to be submitted first
3. **Progress tracking**: Distinguish between "not needed" vs "needed but not ready"
4. **Error prevention**: Avoid trying to submit entities with unmet dependencies

### Payload Fields for Required Accessions
- `expected_*_accession`: Placeholder for the accession that will be assigned
- `requires_*_accession`: Boolean flag indicating the dependency is required
- `requires_project_accession`: For samples
- `requires_study_accession`: For experiments

This enhancement maintains backward compatibility while providing much richer dependency information to broker clients.
