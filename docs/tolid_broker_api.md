> **Status:** Verified current against `app/api/v1/endpoints/broker.py`, `app/services/tolid_service.py`, `app/schemas/tolid.py`, and `tests/unit/endpoints/test_endpoints_broker_tolids.py`.

# ToLID Broker API

This document describes the simplified ToLID flow between Canopy and the external broker worker.

Canopy is the durable store for ToLID state.
The broker is responsible for calling the remote ToLID service.
Canopy does not call the remote ToLID API directly.

Unlike the ENA broker claim flow, the ToLID flow does not use claim, lease, renew, or finalise semantics.

## Overview

The intended flow is:

1. Broker submits a specimen sample to ENA.
2. Broker receives an ENA sample accession such as `ERS123456`.
3. Broker asks Canopy for specimen metadata using that accession.
4. Broker calls the remote ToLID service.
5. Broker reports one of these results back to Canopy:
   - `pending` with `request_id`
   - `assigned` with `tolid`
   - `failed` with `error_message`
6. Broker later fetches `pending` rows from Canopy and retries them as needed.

## Key Semantic Change

Canopy no longer requires a pre-populated ToLID row before the first request.

Absence of a `tolid_request` row means:

- the sample has not yet started the ToLID flow
- the sample may still be requestable if it is a specimen sample and has an ENA sample accession

The `tolid_request` table now represents durable ToLID state once work has actually started or completed.

## Authentication

All ToLID broker endpoints require authentication.

- Read endpoints use the `broker:read` policy.
- Report/update endpoints use the `broker:claim` policy, matching the existing broker write surface.

## Data Model

Canopy stores ToLID request state in `tolid_request`.

Fields:

- `sample_id`: UUID, FK to `sample.id`, unique
- `tolid_external_id`: string, usually the ENA sample accession sent to the ToLID service
- `taxon_id`: integer, FK to `organism.taxon_id`
- `scientific_name`: string nullable
- `tolid`: string nullable
- `request_id`: string nullable
- `status`: `not_requested | pending | assigned | failed`
- `last_requested_at`: timezone-aware timestamp nullable
- `error_message`: string nullable
- `created_at`, `updated_at`

Notes:

- In current usage, Canopy does not need to persist `not_requested` rows ahead of time.
- `not_requested` is mainly a virtual response state returned when the sample is eligible but no ToLID row exists yet.

Indexes:

- unique index on `sample_id`
- index on `status`
- index on `(status, last_requested_at)`
- index on `request_id`

## Eligibility Rules

- ToLID requests are only supported for specimen samples.
- Direct accession lookup validates that the resolved sample has `kind = specimen`.
- The pending endpoint only returns rows whose linked sample has `kind = specimen`.

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/broker/tolids/by-specimen-accession/{specimen_id}` | Resolve a specimen sample from an ENA accession and return current or virtual ToLID state |
| `GET` | `/api/v1/broker/tolids/pending` | List specimen ToLID rows in `pending` state |
| `GET` | `/api/v1/broker/tolids/{sample_id}` | Get one ToLID row by Canopy sample ID, returning virtual `not_requested` state if no row exists but the sample has an accession |
| `POST` | `/api/v1/broker/tolids/{sample_id}/report` | Create or update persisted ToLID state for one sample |

## What No Longer Happens

Canopy no longer auto-creates `not_requested` ToLID rows when sample submission results are reported.

Normal broker sample submission reporting still stores the ENA accession on the submission side, but ToLID state is only persisted when the broker explicitly reports ToLID progress or results.

## 1. Lookup a Specimen Sample by ENA Accession

Returns the specimen sample metadata needed to build a first-time ToLID request.

If a `tolid_request` row already exists, the current persisted state is returned.
If no row exists yet, Canopy returns a virtual/default state with `status = not_requested`.

**Endpoint:** `GET /api/v1/broker/tolids/by-specimen-accession/{specimen_id}`

Example:

```bash
curl -s "http://localhost:8000/api/v1/broker/tolids/by-specimen-accession/ERS123456" \
  -H "Authorization: Bearer $TOKEN"
```

**Response example when no ToLID row exists yet:**

```json
{
  "sample_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "specimen_id": "ERS123456",
  "taxon_id": 1931064,
  "scientific_name": "Manorina melanotis",
  "status": "not_requested",
  "request_id": null,
  "tolid": null,
  "last_requested_at": null,
  "error_message": null,
  "kind": "specimen",
  "sample_payload": {
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "specimen_id": "ATOL-SPEC-001",
    "taxon_id": 1931064
  }
}
```

Response semantics:

- `specimen_id` in this API means the ENA sample accession used for ToLID lookup
- the original Canopy sample record is available in `sample_payload`

## 2. Get Pending ToLIDs

Returns persisted ToLID rows in `pending` state.

**Endpoint:** `GET /api/v1/broker/tolids/pending`

**Query parameters:**

| Name | Required | Description |
|------|----------|-------------|
| `taxon_id` | No | Filter by `organism.taxon_id` |
| `sample_id` | No | Filter to one sample |
| `sample_ids` | No | Filter to a set of samples |
| `requested_before` | No | Return only rows with `last_requested_at` earlier than this timestamp |
| `skip` | No | Pagination offset, default `0` |
| `limit` | No | Pagination limit, default `100`, max `1000` |

**Response example:**

```json
[
  {
    "sample_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "specimen_id": "ERS123456",
    "taxon_id": 1931064,
    "scientific_name": "Manorina melanotis",
    "status": "pending",
    "request_id": "REQ-123",
    "tolid": null,
    "last_requested_at": "2026-06-17T10:15:00Z",
    "error_message": null,
    "kind": "specimen",
    "sample_payload": {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "specimen_id": "ATOL-SPEC-001",
      "taxon_id": 1931064
    }
  }
]
```

## 3. Get One ToLID Row by Sample

Returns one sample’s ToLID state using the Canopy `sample_id`.

If the sample is a specimen sample and Canopy can resolve an ENA sample accession, this endpoint returns:

- persisted state if a `tolid_request` row exists
- virtual `not_requested` state if no row exists yet

**Endpoint:** `GET /api/v1/broker/tolids/{sample_id}`

## 4. Report a ToLID Result

Creates or updates persisted ToLID state for one sample.

If no `tolid_request` row exists yet, Canopy creates it lazily during this call.

**Endpoint:** `POST /api/v1/broker/tolids/{sample_id}/report`

Supported statuses:

- `pending`
- `assigned`
- `failed`

`not_requested` is not accepted by this reporting endpoint.

### Pending

Use when the remote ToLID service has accepted the request but has not yet assigned a ToLID.

**Request body:**

```json
{
  "status": "pending",
  "request_id": "REQ-123",
  "last_requested_at": "2026-06-17T10:15:00Z"
}
```

Behavior:

- creates the row if needed
- stores `request_id`
- sets `status = pending`
- stores `last_requested_at`
- clears `error_message`

### Assigned

Use when the remote ToLID service has assigned a real ToLID.

**Request body:**

```json
{
  "status": "assigned",
  "tolid": "tolExample1",
  "request_id": "REQ-123",
  "last_requested_at": "2026-06-17T10:30:00Z"
}
```

Behavior:

- creates the row if needed
- stores `tolid`
- stores `request_id` if present
- sets `status = assigned`
- stores `last_requested_at`
- clears `error_message`
- mirrors the assigned value onto `sample.tolid`

### Failed

Use when the broker wants Canopy to persist a terminal failure state.

**Request body:**

```json
{
  "status": "failed",
  "request_id": "REQ-123",
  "last_requested_at": "2026-06-17T10:45:00Z",
  "error_message": "Remote service rejected the request"
}
```

Behavior:

- creates the row if needed
- sets `status = failed`
- stores `request_id` if present
- stores `error_message`
- stores `last_requested_at` if present

## Validation Rules

- `assigned` requires `tolid`
- `pending` requires `request_id`
- direct lookup rejects non-specimen samples
- report rejects non-specimen samples
- lazy row creation during report requires Canopy to be able to resolve an ENA sample accession from the sample submission state

## Example curl Commands

```bash
TOKEN=<your_access_token>
SAMPLE_ID=<sample_uuid>
```

### Lookup by accession for the first request

```bash
curl -s "http://localhost:8000/api/v1/broker/tolids/by-specimen-accession/ERS123456" \
  -H "Authorization: Bearer $TOKEN"
```

### Fetch pending rows for retry/polling

```bash
curl -s "http://localhost:8000/api/v1/broker/tolids/pending?taxon_id=1729" \
  -H "Authorization: Bearer $TOKEN"
```

### Report a pending request

```bash
curl -s -X POST "http://localhost:8000/api/v1/broker/tolids/$SAMPLE_ID/report" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "pending",
    "request_id": "REQ-123",
    "last_requested_at": "2026-06-17T10:15:00Z"
  }'
```

### Report an assigned ToLID

```bash
curl -s -X POST "http://localhost:8000/api/v1/broker/tolids/$SAMPLE_ID/report" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "assigned",
    "tolid": "tolExample1",
    "request_id": "REQ-123",
    "last_requested_at": "2026-06-17T10:30:00Z"
  }'
```

## Notes

- `assigned` is treated as terminal.
- `failed` is treated as terminal unless reset manually later.
- Canopy does not decide retry timing for `pending` rows.
- The broker decides when to retry and uses the `pending` endpoint to fetch work.
