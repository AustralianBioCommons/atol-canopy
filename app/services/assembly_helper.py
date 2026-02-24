"""Helper functions for assembly operations."""

import logging
from typing import Dict, List, Set

import yaml

from app.models.experiment import Experiment
from app.models.organism import Organism
from app.models.read import Read
from app.schemas.assembly import AssemblyDataTypes

logger = logging.getLogger(__name__)


def determine_assembly_data_types(experiments: List[Experiment]) -> AssemblyDataTypes:
    """Determine assembly data_types based on experiments.

    Rules:
    - PACBIO_SMRT exists if: platform == "PACBIO_SMRT"
    - OXFORD_NANOPORE exists if: platform == "OXFORD_NANOPORE"
    - Hi-C exists if: platform == "ILLUMINA" AND library_strategy in ("Hi-C", "WGS")

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
        if platform == "PACBIO_SMRT" and library_strategy in ("WGS", "WGA"):
            has_pacbio = True

        # Check for Oxford Nanopore
        if platform == "OXFORD_NANOPORE" and library_strategy in ("WGS", "WGA"):
            has_nanopore = True

        # Check for Hi-C (Illumina + Hi-C or WGS library strategy)
        if platform == "ILLUMINA" and library_strategy in ("HI-C"):
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
        "experiment_count": len(experiments),
    }


def generate_assembly_manifest(
    organism: Organism, reads: List[Read], experiments: List[Experiment], assembly: "Assembly"
) -> str:
    """Generate assembly manifest YAML from organism and reads data.

    Groups reads by platform type (PACBIO_SMRT, Hi-C) and formats as YAML.

    Rules:
    - PACBIO_SMRT: Only include files ending in .ccs.bam or hifi_reads.bam
    - Hi-C: Include read_number and lane_number fields

    Args:
        organism: Organism object
        reads: List of Read objects
        experiments: List of Experiment objects (to determine platform)
        assembly: Assembly object (for tolid/version)

    Returns:
        YAML string formatted as assembly manifest
    """
    logger.info(
        f"Generating manifest for organism: {organism.scientific_name} (tax_id: {organism.tax_id})"
    )
    logger.info(f"Total experiments: {len(experiments)}, Total reads: {len(reads)}")

    # Create experiment_id to platform mapping
    exp_platform_map = {}
    for exp in experiments:
        logger.info(
            f"Experiment {exp.id}: platform={exp.platform}, library_strategy={exp.library_strategy}"
        )
        if exp.platform:
            exp_platform_map[exp.id] = exp.platform.upper()
        if exp.library_strategy:
            exp_platform_map[f"{exp.id}_strategy"] = exp.library_strategy.upper()

    # Group reads by platform
    pacbio_reads = []
    hic_reads = []

    for read in reads:
        if not read.experiment_id:
            logger.debug(f"Read {read.id} has no experiment_id, skipping")
            continue

        platform = exp_platform_map.get(read.experiment_id, "")
        library_strategy = exp_platform_map.get(f"{read.experiment_id}_strategy", "")

        logger.debug(
            f"Read {read.id} (file: {read.file_name}): platform={platform}, library_strategy={library_strategy}"
        )

        # Check for PacBio SMRT reads (only .ccs.bam or hifi_reads.bam)
        if platform == "PACBIO_SMRT" and read.file_name:
            if read.file_name.endswith(".ccs.bam") or read.file_name.endswith("hifi_reads.bam"):
                # TODO remove logging
                logger.info(f"Adding PacBio read: {read.file_name}")
                pacbio_reads.append(
                    {
                        "file_name": read.file_name,
                        "file_checksum": read.file_checksum,
                        "url": read.bioplatforms_url,
                    }
                )
            else:
                logger.debug(
                    f"Skipping PacBio read {read.file_name} - doesn't match .ccs.bam or hifi_reads.bam"
                )

        # Check for Hi-C reads (Illumina + Hi-C or WGS library strategy)
        elif platform == "ILLUMINA" and library_strategy in ("HI-C", "WGS"):
            # TODO remove logging
            logger.info(f"Adding Hi-C read: {read.file_name} (library_strategy={library_strategy})")
            hic_reads.append(
                {
                    "file_name": read.file_name,
                    "file_checksum": read.file_checksum,
                    "url": read.bioplatforms_url,
                    "read_number": read.read_number,
                    "lane_number": read.lane_number,
                }
            )
        else:
            logger.debug(
                f"Read {read.file_name} doesn't match criteria: platform={platform}, library_strategy={library_strategy}"
            )

    # Build manifest structure
    manifest = {
        "scientific_name": organism.scientific_name,
        "taxon_id": organism.tax_id,
        "tolid": assembly.tol_id,
        "version": assembly.version,
        "reads": {},
    }

    if pacbio_reads:
        manifest["reads"]["PACBIO_SMRT"] = pacbio_reads
        logger.info(f"Added {len(pacbio_reads)} PacBio reads to manifest")

    if hic_reads:
        manifest["reads"]["Hi-C"] = hic_reads
        logger.info(f"Added {len(hic_reads)} Hi-C reads to manifest")

    if not pacbio_reads and not hic_reads:
        logger.warning("No reads matched the filtering criteria!")

    # Convert to YAML
    return yaml.dump(manifest, default_flow_style=False, sort_keys=False)
