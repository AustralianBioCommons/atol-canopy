from fastapi import APIRouter

from app.api.v1.endpoints import (
    assemblies,
    auth,
    bpa_initiatives,
    broker,
    experiment_submissions,
    experiments,
    genome_notes,
    organisms,
    projects,
    read_submissions,
    reads,
    sample_submissions,
    samples,
    users,
    xml_export,
)

# Main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(broker.router, prefix="/broker", tags=["broker"])

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
api_router.include_router(
    read_submissions.router, prefix="/read-submissions", tags=["read-submissions"]
)
api_router.include_router(genome_notes.router, prefix="/genome-notes", tags=["genome-notes"])

# XML export endpoints
api_router.include_router(xml_export.router, prefix="/xml-export", tags=["xml-export"])
# api_router.include_router(read_router, prefix="/reads", tags=["reads"])
# api_router.include_router(genome_note_router, prefix="/genome-notes", tags=["genome-notes"])
