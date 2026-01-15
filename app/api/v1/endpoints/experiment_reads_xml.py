"""
XML export endpoint for experiment reads.

This module provides an endpoint to generate XML files for ENA run submissions
associated with a specific experiment.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.models.read import Read
from app.models.user import User
from app.utils.xml_generator import generate_runs_xml

router = APIRouter()


@router.get("/experiments/{experiment_id}/reads/xml", response_class=PlainTextResponse)
def get_experiment_reads_xml(
    *,
    db: Session = Depends(get_db),
    experiment_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Generate ENA run XML for reads associated with a specific experiment.

    Returns the XML representation of all read submission data associated with the experiment.
    """
    # Find the reads for this experiment
    reads = db.query(Read).filter(Read.experiment_id == experiment_id).all()

    if not reads:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No reads found for experiment with ID {experiment_id}",
        )

    # Prepare the data for XML generation
    reads_data = []
    for read in reads:
        if not read.prepared_payload:
            continue

        # Get the run accession if available
        accession = read.prepared_payload.get("run_accession")

        # Use the BPA dataset ID as the alias if available
        alias = read.bpa_dataset_id if read.bpa_dataset_id else f"read_{read.id}"

        reads_data.append(
            {"prepared_payload": read.prepared_payload, "alias": alias, "accession": accession}
        )

    if not reads_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="None of the reads for this experiment have prepared_payload data",
        )

    # Generate XML using the utility function
    xml_content = generate_runs_xml(reads_data)

    return xml_content
