from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    assemblies,
    auth,
    bpa_initiatives,
    broker,
    experiment_submissions,
    experiments,
    genome_notes,
    organisms,
    projects,
    qc_reads,
    reads,
    sample_submissions,
    samples,
    taxonomy_info,
    users,
)

# Main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(broker.router, prefix="/broker", tags=["broker"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

# Core entity routers
api_router.include_router(organisms.router, prefix="/organisms", tags=["organisms"])
api_router.include_router(samples.router, prefix="/samples", tags=["samples"])
api_router.include_router(
    sample_submissions.router, prefix="/sample-submissions", tags=["sample-submissions"]
)
api_router.include_router(experiments.router, prefix="/experiments", tags=["experiments"])
api_router.include_router(
    experiment_submissions.router, prefix="/experiment-submissions", tags=["experiment-submissions"]
)
api_router.include_router(assemblies.router, prefix="/assemblies", tags=["assemblies"])
api_router.include_router(
    bpa_initiatives.router, prefix="/bpa-initiatives", tags=["bpa-initiatives"]
)
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(reads.router, prefix="/reads", tags=["reads"])
api_router.include_router(qc_reads.router, prefix="/qc-reads", tags=["qc-reads"])
api_router.include_router(genome_notes.router, prefix="/genome-notes", tags=["genome-notes"])
api_router.include_router(taxonomy_info.router, prefix="/taxonomy-info", tags=["taxonomy-info"])

# api_router.include_router(read_router, prefix="/reads", tags=["reads"])
# api_router.include_router(genome_note_router, prefix="/genome-notes", tags=["genome-notes"])
