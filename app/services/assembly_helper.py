"""Helper functions for assembly operations."""

import logging
from typing import Any, Dict, List, Set

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
        if platform == "ILLUMINA" and library_strategy in ("HI-C", "WGS"):
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


def _normalize_read_number(read_number: str | None) -> str | None:
    """Normalize read_number to 'r1' or 'r2'."""
    if read_number is None:
        return None
    normalized = read_number.strip().lower().lstrip("r")
    if normalized == "1":
        return "r1"
    if normalized == "2":
        return "r2"
    return None


def generate_assembly_manifest(
    organism: Organism,
    reads: List[Read],
    experiments: List[Experiment],
    tol_id: str | None,
    version: int,
    sample_metadata_by_id: Dict[str, Dict[str, Any]] | None = None,
) -> str:
    """Generate assembly manifest YAML from organism and reads data.

    Groups reads by bpa_package_id (from Experiment), then by platform type.

    Rules:
    - PACBIO_SMRT: Only include files ending in .ccs.bam or hifi_reads.bam
    - Hi-C: Split reads into r1/r2 groups by read_number

    Args:
        organism: Organism object
        reads: List of Read objects
        experiments: List of Experiment objects (to determine platform)
        tol_id: ToL ID for the assembly (optional)
        version: Assembly version number
        sample_metadata_by_id: Sample metadata keyed by sample.id as string (optional)

    Returns:
        YAML string formatted as assembly manifest
    """
    logger.info(
        f"Generating manifest for organism: {organism.scientific_name} (taxon_id: {organism.taxon_id})"
    )
    logger.info(f"Total experiments: {len(experiments)}, Total reads: {len(reads)}")

    # Build experiment info map: experiment.id → metadata
    exp_info_map = {}
    for exp in experiments:
        logger.info(
            f"Experiment {exp.id}: platform={exp.platform}, library_strategy={exp.library_strategy}"
        )
        exp_info_map[exp.id] = {
            "platform": exp.platform.upper() if exp.platform else "",
            "library_strategy": exp.library_strategy.upper() if exp.library_strategy else "",
            "bpa_package_id": exp.bpa_package_id,
            "base_url": getattr(exp, "base_url", None),
            "sample_id": str(exp.sample_id) if getattr(exp, "sample_id", None) else None,
        }

    # Group reads by bpa_package_id per platform
    pacbio_by_package: Dict[str, Any] = {}
    hic_by_package: Dict[str, Any] = {}

    for read in reads:
        if not read.experiment_id:
            logger.debug(f"Read {read.id} has no experiment_id, skipping")
            continue

        exp_info = exp_info_map.get(read.experiment_id)
        if not exp_info:
            logger.debug(f"Read {read.id} has no matching experiment, skipping")
            continue

        platform = exp_info["platform"]
        library_strategy = exp_info["library_strategy"]
        bpa_package_id = exp_info["bpa_package_id"]
        sample_id = exp_info["sample_id"]
        sample_meta = (sample_metadata_by_id or {}).get(sample_id, {}) if sample_id else {}

        logger.debug(
            f"Read {read.id} (file: {read.file_name}): platform={platform}, library_strategy={library_strategy}"
        )

        # PacBio SMRT reads (only .ccs.bam or hifi_reads.bam)
        if platform == "PACBIO_SMRT" and read.file_name:
            if read.file_name.endswith(".ccs.bam") or read.file_name.endswith("hifi_reads.bam"):
                logger.info(f"Adding PacBio read: {read.file_name}")
                if bpa_package_id not in pacbio_by_package:
                    entry: Dict[str, Any] = {
                        "sample_id": sample_id,
                        "bpa_sample_id": sample_meta.get("bpa_sample_id"),
                        "specimen_id": sample_meta.get("specimen_id"),
                        "resources": [],
                    }
                    if exp_info["base_url"]:
                        entry["base_url"] = exp_info["base_url"]
                    pacbio_by_package[bpa_package_id] = entry
                pacbio_by_package[bpa_package_id]["resources"].append(
                    {"md5sum": read.file_checksum, "url": read.bioplatforms_url}
                )
            else:
                logger.debug(
                    f"Skipping PacBio read {read.file_name} - doesn't match .ccs.bam or hifi_reads.bam"
                )

        # Hi-C reads (Illumina + Hi-C or WGS library strategy)
        elif platform == "ILLUMINA" and library_strategy in ("HI-C", "WGS"):
            logger.info(f"Adding Hi-C read: {read.file_name} (library_strategy={library_strategy})")
            if bpa_package_id not in hic_by_package:
                hic_by_package[bpa_package_id] = {
                    "sample_id": sample_id,
                    "bpa_sample_id": sample_meta.get("bpa_sample_id"),
                    "specimen_id": sample_meta.get("specimen_id"),
                    "resources": {"r1": [], "r2": []},
                }
            rkey = _normalize_read_number(read.read_number)
            if rkey in ("r1", "r2"):
                hic_by_package[bpa_package_id]["resources"][rkey].append(
                    {
                        "url": read.bioplatforms_url,
                        "md5sum": read.file_checksum,
                        "lane_number": read.lane_number,
                    }
                )
            else:
                logger.debug(
                    f"Hi-C read {read.file_name} has unrecognized read_number={read.read_number}, skipping"
                )
        else:
            logger.debug(
                f"Read {read.file_name} doesn't match criteria: platform={platform}, library_strategy={library_strategy}"
            )

    # Build manifest structure
    manifest = {
        "scientific_name": organism.scientific_name,
        "taxon_id": organism.taxon_id,
        "tolid": tol_id,
        "version": version,
        "reads": {},
    }

    if pacbio_by_package:
        manifest["reads"]["PACBIO_SMRT"] = pacbio_by_package
        logger.info(f"Added {len(pacbio_by_package)} PacBio packages to manifest")

    if hic_by_package:
        manifest["reads"]["Hi-C"] = hic_by_package
        logger.info(f"Added {len(hic_by_package)} Hi-C packages to manifest")

    if not pacbio_by_package and not hic_by_package:
        logger.warning("No reads matched the filtering criteria!")

    # Convert to YAML
    return yaml.dump(manifest, default_flow_style=False, sort_keys=False)
