"""
XML export endpoints for ENA submissions.

This module provides endpoints to generate XML files for various ENA submission types
(samples, experiments, runs, etc.) from the internal database records.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.models.sample import SampleSubmission
from app.models.experiment import Experiment, ExperimentSubmission
from app.models.read import Read
from app.models.user import User
from app.models.organism import Organism
from app.utils.xml_generator import (
    generate_sample_xml, 
    generate_experiment_xml, 
    generate_run_xml, 
    generate_runs_xml
)

router = APIRouter()

#
# Sample XML endpoints
#

@router.get("/samples/{sample_id}", response_class=PlainTextResponse)
def get_sample_xml(
    *,
    db: Session = Depends(get_db),
    sample_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Generate ENA sample XML for a specific sample.
    
    Returns the XML representation of the sample submission data.
    """
    # Find the submission record for this sample
    sample_submission = db.query(SampleSubmission).filter(
        SampleSubmission.sample_id == sample_id
    ).first()
    
    if not sample_submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample submission data not found",
        )
    
    if not sample_submission.prepared_payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sample has no prepared_payload data",
        )
        
    # Get the organism data
    organism_id = sample_submission.organism_id
    if not organism_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sample_submitted object missing organism_id",
        )
        
    organism = db.query(Organism).filter(Organism.id == organism_id).first()
    
    if not organism:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organism with id {organism_id} not found",
        )
    
    # Generate XML using the utility function
    xml_content = generate_sample_xml(
        organism=organism,
        prepared_payload=sample_submission.prepared_payload,
        alias=sample_submission.sample.bpa_sample_id if sample_submission.sample else f"sample_{sample_submission.sample_id}",
        accession=sample_submission.sample.sample_accession if sample_submission.sample and sample_submission.sample.sample_accession else None
    )
    
    return xml_content


@router.get("/experiments/package/{bpa_package_id}/sample", response_class=PlainTextResponse)
def get_experiment_sample_xml(
    *,
    db: Session = Depends(get_db),
    bpa_package_id: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Generate ENA sample XML for samples associated with a specific experiment package.
    
    Returns the XML representation of all sample submission data associated with the experiment.
    """
    # Find the experiment with the given bpa_package_id
    experiment = db.query(Experiment).filter(Experiment.bpa_package_id == bpa_package_id).first()
    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment with bpa_package_id {bpa_package_id} not found"
        )
    
    # Get the sample_id from the experiment
    if not experiment.sample_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment with bpa_package_id {bpa_package_id} has no associated sample"
        )
    
    # Find the submission records for this sample
    sample_submission = db.query(SampleSubmission).filter(
        SampleSubmission.sample_id == experiment.sample_id
    ).first()
    
    if not sample_submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No submission sample records found for experiment with bpa_package_id {bpa_package_id}"
        )
    
    if not sample_submission.prepared_payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sample has no prepared_payload data",
        )
    
    # Get the organism data
    organism_id = sample_submission.organism_id
    if not organism_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sample_submitted object missing organism_id",
        )
        
    organism = db.query(Organism).filter(Organism.id == organism_id).first()
    
    if not organism:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organism with id {organism_id} not found",
        )
    
    # Generate XML using the utility function
    xml_content = generate_sample_xml(
        organism=organism,
        prepared_payload=sample_submission.prepared_payload,
        alias=sample_submission.sample.bpa_sample_id if sample_submission.sample else f"sample_{sample_submission.sample_id}",
        accession=sample_submission.sample.sample_accession if sample_submission.sample and sample_submission.sample.sample_accession else None
    )
    
    return xml_content


#
# Experiment XML endpoints
#

@router.get("/experiments/{experiment_id}", response_class=PlainTextResponse)
def get_experiment_xml(
    *,
    db: Session = Depends(get_db),
    experiment_id: UUID,
    study_accession: Optional[str] = Query(None, description="Study accession to use in the XML"),
    study_alias: Optional[str] = Query(None, description="Study refname to use in the XML"),
    sample_accession: Optional[str] = Query(None, description="Sample accession to use in the XML"),
    sample_alias: Optional[str] = Query(None, description="Sample refname to use in the XML"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Generate ENA experiment XML for a specific experiment.
    
    Returns the XML representation of the experiment submission data.
    """
    # Find the submission record for this experiment
    experiment_submission = db.query(ExperimentSubmission).filter(
        ExperimentSubmission.experiment_id == experiment_id
    ).first()
    
    if not experiment_submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment submission data not found",
        )
    
    if not experiment_submission.prepared_payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Experiment has no prepared_payload data",
        )
    
    # Generate XML using the utility function
    xml_content = generate_experiment_xml(
        prepared_payload=experiment_submission.prepared_payload,
        alias=experiment_submission.prepared_payload.get("alias"),
        study_accession=study_accession,
        study_alias=study_alias,
        sample_accession=sample_accession,
        sample_alias=sample_alias,
        accession=experiment_submission.experiment_accession if experiment_submission.experiment_accession else None
    )
    
    return xml_content


@router.get("/experiments/package/{bpa_package_id}", response_class=PlainTextResponse)
def get_experiment_by_package_id_xml(
    *,
    db: Session = Depends(get_db),
    bpa_package_id: str,
    study_accession: Optional[str] = Query(None, description="Study accession to use in the XML"),
    study_alias: Optional[str] = Query(None, description="Study refname to use in the XML"),
    sample_accession: Optional[str] = Query(None, description="Sample accession to use in the XML"),
    sample_alias: Optional[str] = Query(None, description="Sample refname to use in the XML"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Generate ENA experiment XML for a specific experiment package.
    
    Returns the XML representation of the experiment submission data associated with the package ID.
    """
    # Find the experiment with the given bpa_package_id
    experiment = db.query(Experiment).filter(Experiment.bpa_package_id == bpa_package_id).first()
    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment with bpa_package_id {bpa_package_id} not found"
        )
    
    # Find the submission records for this experiment
    experiment_submission = db.query(ExperimentSubmission).filter(
        ExperimentSubmission.experiment_id == experiment.id
    ).first()
    
    if not experiment_submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No submission experiment records found for experiment with bpa_package_id {bpa_package_id}"
        )
    
    if not experiment_submission.prepared_payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Experiment has no prepared_payload data",
        )
    
    # Generate XML using the utility function
    xml_content = generate_experiment_xml(
        prepared_payload=experiment_submission.prepared_payload,
        alias=experiment_submission.prepared_payload.get("alias"),
        study_accession=study_accession,
        study_alias=study_alias,
        sample_accession=sample_accession,
        sample_alias=sample_alias,
        accession=experiment_submission.experiment_accession if experiment_submission.experiment_accession else None
    )
    
    return xml_content


#
# Run XML endpoints
#

@router.get("/reads/{read_id}", response_class=PlainTextResponse)
def get_read_xml(
    *,
    db: Session = Depends(get_db),
    read_id: UUID,
    experiment_accession: Optional[str] = Query(None, description="Experiment accession to use in the XML"),
    experiment_alias: Optional[str] = Query(None, description="Experiment refname to use in the XML"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Generate ENA run XML for a specific read.
    
    Returns the XML representation of the read submission data.
    """
    # Find the read record
    read = db.query(Read).filter(Read.id == read_id).first()
    
    if not read:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Read not found",
        )
    
    if not read.prepared_payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Read has no prepared_payload data",
        )
    
    # Generate XML using the utility function
    xml_content = generate_run_xml(
        prepared_payload=read.prepared_payload,
        alias=read.bpa_dataset_id if read.bpa_dataset_id else f"read_{read_id}",
        experiment_accession=experiment_accession,
        experiment_alias=experiment_alias,
        accession=read.prepared_payload.get("run_accession")
    )
    
    return xml_content


@router.get("/reads", response_class=PlainTextResponse)
def get_reads_xml(
    *,
    db: Session = Depends(get_db),
    read_ids: List[UUID] = Query(None, description="List of read IDs to include in the XML"),
    experiment_id: Optional[UUID] = Query(None, description="Filter by experiment ID"),
    status: Optional[str] = Query(None, description="Filter by submission status"),
    experiment_accession: Optional[str] = Query(None, description="Experiment accession to use in the XML"),
    experiment_alias: Optional[str] = Query(None, description="Experiment refname to use in the XML"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Generate ENA run XML for multiple reads.
    
    Returns the XML representation of the read submission data for all specified reads.
    If no read_ids are provided, all reads matching the filters are included.
    """
    # Build the query
    query = db.query(Read)
    
    # Apply filters if provided
    if read_ids:
        query = query.filter(Read.id.in_(read_ids))
    
    if experiment_id:
        query = query.filter(Read.experiment_id == experiment_id)
    
    if status:
        query = query.filter(Read.status == status)
    
    # Get the reads
    reads = query.all()
    
    if not reads:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No read data found matching the criteria",
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
            
        reads_data.append({
            "prepared_payload": read.prepared_payload,
            "alias": alias,
            "accession": accession
        })
    
    if not reads_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="None of the selected reads have prepared_payload data",
        )
    
    # Generate XML using the utility function
    xml_content = generate_runs_xml(
        runs_data=reads_data, 
        experiment_accession=experiment_accession, 
        experiment_alias=experiment_alias
    )
    
    return xml_content


@router.get("/experiments/{experiment_id}/reads", response_class=PlainTextResponse)
def get_experiment_reads_xml(
    *,
    db: Session = Depends(get_db),
    experiment_id: UUID,
    experiment_accession: Optional[str] = Query(None, description="Experiment accession to use in the XML"),
    experiment_alias: Optional[str] = Query(None, description="Experiment refname to use in the XML"),
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
            detail=f"No reads found for experiment with ID {experiment_id}"
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
            
        reads_data.append({
            "prepared_payload": read.prepared_payload,
            "alias": alias,
            "accession": accession
        })
    
    if not reads_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="None of the reads for this experiment have prepared_payload data",
        )
    
    # Generate XML using the utility function
    xml_content = generate_runs_xml(
        runs_data=reads_data, 
        experiment_accession=experiment_accession, 
        experiment_alias=experiment_alias
    )
    
    return xml_content
