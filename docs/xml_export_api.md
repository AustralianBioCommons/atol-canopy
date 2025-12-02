# XML Export API Documentation

This document provides information about the XML export functionality for ENA (European Nucleotide Archive) submissions in the AToL Database API.

## Overview

The XML Export API allows you to generate ENA-compliant XML files for sample, experiment, and run submissions. These XML files can be used for submitting data to ENA through their submission portal or API.

## Endpoints

### Sample XML Export

#### Get XML for a Single Sample

```
GET /api/v1/xml-export/samples/{sample_id}/xml
```

Generates ENA-compliant XML for a specific sample identified by its UUID.

**Parameters:**
- `sample_id`: UUID of the sample

**Response:**
- Content-Type: `text/plain`
- Body: XML content for the sample

#### Get XML for Multiple Samples

```
GET /api/v1/xml-export/samples/xml
```

Generates ENA-compliant XML for multiple samples based on provided filters.

**Query Parameters:**
- `sample_ids`: (Optional) List of sample UUIDs to include
- `status`: (Optional) Filter by submission status

**Response:**
- Content-Type: `text/plain`
- Body: XML content for all matching samples

#### Get XML for Samples Associated with an Experiment

```
GET /api/v1/xml-export/experiments/package/{bpa_package_id}/samples/xml
```

Generates ENA-compliant XML for samples associated with a specific experiment package.

**Parameters:**
- `bpa_package_id`: BPA package ID of the experiment

**Response:**
- Content-Type: `text/plain`
- Body: XML content for associated samples

### Experiment XML Export

#### Get XML for a Single Experiment

```
GET /api/v1/xml-export/experiments/{experiment_id}/xml
```

Generates ENA-compliant XML for a specific experiment identified by its UUID.

**Parameters:**
- `experiment_id`: UUID of the experiment

**Response:**
- Content-Type: `text/plain`
- Body: XML content for the experiment

#### Get XML for Multiple Experiments

```
GET /api/v1/xml-export/experiments/xml
```

Generates ENA-compliant XML for multiple experiments based on provided filters.

**Query Parameters:**
- `experiment_ids`: (Optional) List of experiment UUIDs to include
- `status`: (Optional) Filter by submission status

**Response:**
- Content-Type: `text/plain`
- Body: XML content for all matching experiments

#### Get XML for an Experiment by Package ID

```
GET /api/v1/xml-export/experiments/package/{bpa_package_id}/xml
```

Generates ENA-compliant XML for a specific experiment identified by its BPA package ID.

**Parameters:**
- `bpa_package_id`: BPA package ID of the experiment

**Response:**
- Content-Type: `text/plain`
- Body: XML content for the experiment

### Run XML Export

#### Get XML for a Single Read/Run

```
GET /api/v1/xml-export/reads/{read_id}/xml
```

Generates ENA-compliant XML for a specific read/run identified by its UUID.

**Parameters:**
- `read_id`: UUID of the read

**Response:**
- Content-Type: `text/plain`
- Body: XML content for the read/run

#### Get XML for Multiple Reads/Runs

```
GET /api/v1/xml-export/reads/xml
```

Generates ENA-compliant XML for multiple reads/runs based on provided filters.

**Query Parameters:**
- `read_ids`: (Optional) List of read UUIDs to include
- `experiment_id`: (Optional) Filter by experiment ID
- `status`: (Optional) Filter by submission status

**Response:**
- Content-Type: `text/plain`
- Body: XML content for all matching reads/runs

#### Get XML for Reads/Runs Associated with an Experiment

```
GET /api/v1/xml-export/experiments/{experiment_id}/reads/xml
```

Generates ENA-compliant XML for reads/runs associated with a specific experiment.

**Parameters:**
- `experiment_id`: UUID of the experiment

**Response:**
- Content-Type: `text/plain`
- Body: XML content for associated reads/runs

## XML Structure

### Sample XML

The generated sample XML follows the ENA sample schema and includes:

- Sample identifiers
- Title
- Taxonomy information (taxon ID, scientific name, common name)
- Description
- Sample attributes
- ENA checklist reference

### Experiment XML

The generated experiment XML follows the ENA experiment schema and includes:

- Experiment identifiers
- Title
- Study reference
- Design description and library information
- Platform and instrument model
- Experiment attributes

### Run XML

The generated run XML follows the ENA run schema and includes:

- Run identifiers
- Experiment reference
- Platform and instrument model
- Data block with file information (filename, checksum, filetype, etc.)

## Usage Example

To retrieve XML for a specific experiment:

```
curl -X GET "http://localhost:8000/api/v1/xml-export/experiments/{experiment_id}/xml" -H "Authorization: Bearer {your_token}"
```

Replace `{experiment_id}` with the UUID of your experiment and `{your_token}` with your authentication token.

## Notes

- All endpoints require authentication
- The XML is generated from the `prepared_payload` field in the respective database tables
- If a record has no `prepared_payload` data, a 400 Bad Request error will be returned
- The XML is formatted according to ENA submission requirements
