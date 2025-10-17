# Canopy: A Metadata Tracking System for the Australian Tree of Life (AToL) data

Canopy is a FastAPI backend used to track and manage genomic data for the Australian Tree of Life (AToL).

## Overview

This system manages metadata for core biological entities:
- Organism
- Sample
- Experiment
- Assembly
- BPA Initiative
- Project
- Reads
- Genome Note

The system follows a design pattern with three tables per core entity:
- Main table (current state)
- Submission table (staged for submission)
- Fetched table (immutable history)

## Features

- JWT-based authentication with role-based access control
- RESTful API endpoints for all core biological entities
- Bulk import API endpoints for organisms, samples, and experiments
- PostgreSQL database with UUID primary keys and JSONB fields
- Docker and Docker Compose deployment

## Tech Stack

- FastAPI
- SQLAlchemy ORM
- Pydantic for data validation
- PostgreSQL
- JWT authentication (python-jose)
- Password hashing (passlib)
- Docker & Docker Compose

## Project Structure

```
app/
├── api/
│   └── v1/
│       ├── endpoints/
│       │   ├── assemblies.py
│       │   ├── auth.py
│       │   ├── projects.py
│       │   ├── bpa_initiatives.py
│       │   ├── experiments.py
│       │   ├── genome_notes.py
│       │   ├── organisms.py
│       │   ├── reads.py
│       │   ├── samples.py
│       │   └── users.py
│       └── api.py
├── core/
│   ├── dependencies.py
│   ├── security.py
│   └── settings.py
├── db/
│   └── session.py
├── models/
│   ├── assembly.py
│   ├── project.py
│   ├── bpa_initiative.py
│   ├── experiment.py
│   ├── genome_note.py
│   ├── organism.py
│   ├── read.py
│   ├── sample.py
│   └── user.py
├── schemas/
│   ├── assembly.py
│   ├── project.py
│   ├── bpa_initiative.py
│   ├── experiment.py
│   ├── genome_note.py
│   ├── organism.py
│   ├── read.py
│   ├── sample.py
│   └── user.py
└── main.py
```

## Getting Started

### Prerequisites

- Docker and Docker Compose

### Running the Application

1. Clone the repository
2. Set up your environment variables or use the defaults in docker-compose.yml
3. Run the application:

```bash
docker-compose up -d
```

## Bulk Import API

The system provides API endpoints for bulk importing organisms, samples, and experiments. These endpoints allow you to import data in the same format as the standalone import script but through authenticated API calls.

### Bulk Import Endpoints

- `/api/v1/organisms/bulk-import` - Bulk import organisms
- `/api/v1/samples/bulk-import` - Bulk import samples
- `/api/v1/experiments/bulk-import` - Bulk import experiments

All bulk import endpoints:
- Require authentication with 'curator' or 'admin' role
- Accept JSON data in the same format as the standalone import script
- Return counts of created and skipped records

### Example Client

An example Python client for the bulk import API is available in `examples/bulk_import_client.py`.

```bash
# Import all data from default locations
python examples/bulk_import_client.py --username admin --password password --all
```

For detailed documentation on the bulk import API, see `docs/bulk_import_api.md`.

4. Access the API documentation at http://localhost:8000/docs

### Authentication

The API uses JWT tokens for authentication. To authenticate:

1. Create a user or use a default admin user
2. Get a token from `/auth/login` endpoint
3. Use the token in the Authorization header: `Bearer {token}`

## API Documentation

Once the application is running, you can access the interactive API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Role-Based Access Control

The system implements role-based access control with the following roles:

- **user**: Basic read access to data
- **curator**: Can create and update biological entities
- **admin**: Full access to all endpoints
- **superuser**: Special role with delete permissions

## Development

### Setting Up a Development Environment

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export DATABASE_URI=postgresql://postgres:postgres@localhost:5432/atol_db
export JWT_SECRET_KEY=your_secret_key
```

4. Run the application:
```bash
uvicorn app.main:app --reload
```

## License

This project is licensed under the MIT License.
