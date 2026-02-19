"""Helper functions for assembly operations."""
from typing import List, Set

from app.models.experiment import Experiment
from app.schemas.assembly import AssemblyDataTypes


def determine_assembly_data_types(experiments: List[Experiment]) -> AssemblyDataTypes:
    """Determine assembly data_types based on experiments.
    
    Rules:
    - PACBIO_SMRT exists if: platform == "PACBIO_SMRT"
    - OXFORD_NANOPORE exists if: platform == "OXFORD_NANOPORE"
    - Hi-C exists if: platform == "ILLUMINA" AND library_strategy == "Hi-C"
    
    Args:
        experiments: List of Experiment objects
        
    Returns:
        AssemblyDataTypes enum value based on detected platforms
        
    Raises:
        ValueError: If no valid sequencing platforms are detected
    """
    has_pacbio = False
    has_nanopore = False
    has_hic = False
    
    for exp in experiments:
        platform = exp.platform.upper() if exp.platform else ""
        library_strategy = exp.library_strategy.upper() if exp.library_strategy else ""
        
        # Check for PacBio
        if platform == "PACBIO_SMRT":
            has_pacbio = True
        
        # Check for Oxford Nanopore
        if platform == "OXFORD_NANOPORE":
            has_nanopore = True
        
        # Check for Hi-C (Illumina + Hi-C library strategy)
        if platform == "ILLUMINA" and library_strategy == "HI-C":
            has_hic = True
    
    # Determine the appropriate enum value based on combinations
    if has_pacbio and has_nanopore and has_hic:
        return AssemblyDataTypes.PACBIO_SMRT_OXFORD_NANOPORE_HIC
    elif has_pacbio and has_nanopore:
        return AssemblyDataTypes.PACBIO_SMRT_OXFORD_NANOPORE
    elif has_pacbio and has_hic:
        return AssemblyDataTypes.PACBIO_SMRT_HIC
    elif has_nanopore and has_hic:
        return AssemblyDataTypes.OXFORD_NANOPORE_HIC
    elif has_pacbio:
        return AssemblyDataTypes.PACBIO_SMRT
    elif has_nanopore:
        return AssemblyDataTypes.OXFORD_NANOPORE
    else:
        raise ValueError(
            "No valid sequencing platforms detected in experiments. "
            "Expected PACBIO_SMRT, OXFORD_NANOPORE, or ILLUMINA with Hi-C library strategy."
        )


def get_detected_platforms(experiments: List[Experiment]) -> dict:
    """Get a summary of detected platforms for debugging/logging.
    
    Args:
        experiments: List of Experiment objects
        
    Returns:
        Dictionary with platform detection details
    """
    platforms: Set[str] = set()
    library_strategies: Set[str] = set()
    
    for exp in experiments:
        if exp.platform:
            platforms.add(exp.platform)
        if exp.library_strategy:
            library_strategies.add(exp.library_strategy)
    
    return {
        "platforms": list(platforms),
        "library_strategies": list(library_strategies),
        "experiment_count": len(experiments)
    }
