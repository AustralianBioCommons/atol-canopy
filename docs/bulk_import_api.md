# Bulk Import API Documentation

This document describes how to use the bulk import API endpoints to import organisms, samples, and experiments into the database.

## Authentication

All bulk import endpoints require authentication and the user must have either the 'curator' or 'admin' role.

## Endpoints Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/organisms/bulk-import` | POST | Bulk import organisms |
| `/api/v1/samples/bulk-import` | POST | Bulk import samples |
| `/api/v1/experiments/bulk-import` | POST | Bulk import experiments |

## Request Format

### Bulk Import Organisms

**Endpoint:** `/api/v1/organisms/bulk-import`

**Request Body:**
```json
{
  "organisms": {
    "123456": {
      "taxon_id": 123456,
      "scientific_name": "Organism scientific name",
      "other_field": "value",
      ...
    },
    "789012": {
      ...
    }
  }
}
```

The request body should match the format of the JSON file in `data/unique_organisms.json`. Each organism is keyed by `taxon_id` and must contain at least `taxon_id` and `scientific_name`.

**Response:**
```json
{
  "created_count": 10,
  "skipped_count": 2,
  "message": "Organism import complete. Created: 10, Skipped: 2"
}
```

### Bulk Import Samples

**Endpoint:** `/api/v1/samples/bulk-import`

**Request Body:**
```json
{
  "samples": {
    "bpa_sample_id_1": {
      "taxon_id": 123456,
      "other_field": "value",
      ...
    },
    "bpa_sample_id_2": {
      ...
    }
  }
}
```

The request body should match the format of the JSON file in `data/unique_samples.json`. Each sample is identified by its `bpa_sample_id` and can include `taxon_id` to link it to an organism.

**Response:**
```json
{
  "created_count": 15,
  "skipped_count": 3,
  "message": "Sample import complete. Created samples: 15, Created submission records: 15, Skipped: 3"
}
```

### Bulk Import Experiments

**Endpoint:** `/api/v1/experiments/bulk-import`

**Request Body:**
```json
{
  "experiments": {
    "bpa_package_id_1": {
      "bpa_sample_id": "bpa_sample_id_1",
      "other_field": "value",
      ...
    },
    "bpa_package_id_2": {
      ...
    }
  }
}
```

The request body should match the format of the JSON file in `data/experiments.json`. Each experiment is identified by its `bpa_package_id` and must contain a `bpa_sample_id` to link it to a sample.

**Response:**
```json
{
  "created_count": 20,
  "skipped_count": 5,
  "message": "Experiment import complete. Created experiments: 20, Created submission records: 20, Skipped: 5"
}
```

## Import Order

When importing data, follow this order to ensure proper relationships:

1. Import organisms first
2. Import samples second (they may reference organisms)
3. Import experiments last (they reference samples)

## Error Handling

- If an entity already exists (by its unique key), it will be skipped
- If required fields are missing, the entity will be skipped
- If referenced entities don't exist (e.g., a sample references a non-existent organism), the entity will still be created but without the relationship

## Example Usage with curl

### Import Organisms
```bash
curl -X POST "http://localhost:8000/api/v1/organisms/bulk-import" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d @data/unique_organisms.json
```

### Import Samples
```bash
curl -X POST "http://localhost:8000/api/v1/samples/bulk-import" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d @data/unique_samples.json
```

### Import Experiments
```bash
curl -X POST "http://localhost:8000/api/v1/experiments/bulk-import" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d @data/experiments.json
```

## Converting Standalone Script Data to API Format

If you have data in a different format, you may need to transform it to match the expected format for these endpoints. The format should match the JSON files used by the standalone import script:

- `data/unique_organisms.json`
- `data/unique_samples.json`
- `data/experiments.json`
