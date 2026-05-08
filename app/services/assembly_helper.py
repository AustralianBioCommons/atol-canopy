"""Helper functions for assembly operations."""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from app.models.experiment import Experiment
from app.models.organism import Organism
from app.models.read import Read
from app.schemas.assembly import AssemblyDataTypes

logger = logging.getLogger(__name__)


def _detect_assembly_data_type_flags(experiments: List[Experiment]) -> Tuple[bool, bool, bool]:
    """Return booleans for PacBio, ONT, and Hi-C using assembly classification rules."""
    has_pacbio = False
    has_nanopore = False
    has_hic = False

    for exp in experiments:
        platform = exp.platform.upper() if exp.platform else ""
        library_strategy = exp.library_strategy.upper() if exp.library_strategy else ""

        if platform == "PACBIO_SMRT" and library_strategy in ("WGS", "WGA"):
            has_pacbio = True
        if platform == "OXFORD_NANOPORE" and library_strategy in ("WGS", "WGA"):
            has_nanopore = True
        if platform == "ILLUMINA" and library_strategy == "HI-C":
            has_hic = True

    return has_pacbio, has_nanopore, has_hic


def get_available_assembly_data_types(experiments: List[Experiment]) -> List[str]:
    """Return atomic data types available for a specimen sample.

    This is used by discovery flows, so a sample with only Hi-C data should still
    report ["Hi-C"] even though that combination is not sufficient for creating an
    assembly intent on its own.
    """
    has_pacbio, has_nanopore, has_hic = _detect_assembly_data_type_flags(experiments)
    available_data_types: List[str] = []

    if has_pacbio:
        available_data_types.append("PACBIO_SMRT")
    if has_nanopore:
        available_data_types.append("OXFORD_NANOPORE")
    if has_hic:
        available_data_types.append("Hi-C")

    return available_data_types


def determine_assembly_data_types(experiments: List[Experiment]) -> AssemblyDataTypes:
    """Determine assembly data_types based on experiments.

    Rules:
    - PACBIO_SMRT exists if: platform == "PACBIO_SMRT"
    - OXFORD_NANOPORE exists if: platform == "OXFORD_NANOPORE"
    - Hi-C exists if: platform == "ILLUMINA" AND library_strategy == "Hi-C"

    Raises:
        ValueError: If no valid sequencing platforms are detected
    """
    has_pacbio, has_nanopore, has_hic = _detect_assembly_data_type_flags(experiments)

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
            "No valid data types detected in experiments. "
            "Expected PACBIO_SMRT (with or without Hi-C), OXFORD_NANOPORE (with or without Hi-C), or ILLUMINA with Hi-C."
        )


def get_detected_platforms(experiments: List[Experiment]) -> dict:
    """Get a summary of detected platforms for debugging/logging."""
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


def generate_assembly_manifest_json(
    organism: Organism,
    reads: List[Read],
    experiments: List[Experiment],
    tol_id: str | None,
    version: int,
    long_read_sample_id: UUID,
    hic_sample_id: Optional[UUID] = None,
    sample_metadata_by_id: Dict[str, Dict[str, Any]] | None = None,
    sequencing_sample_to_specimen_sample_id: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """Generate an assembly manifest as a JSON-serialisable dict.

    Reads are routed to sections based on which specimen sample they belong to:
    - Reads from long_read_sample_id experiments → PACBIO_SMRT or OXFORD_NANOPORE section
    - Reads from hic_sample_id experiments → Hi-C section (omitted when hic_sample_id is None)

    PacBio filtering: only files ending in .ccs.bam or hifi_reads.bam are included.
    ONT: all reads are included.
    Hi-C: reads are split into r1/r2 by read_number and include lane_number.

    Args:
        organism: Organism object
        reads: Combined list of Read objects from both specimen samples
        experiments: Combined list of Experiment objects from both specimen samples
        tol_id: ToL ID for the assembly (optional)
        version: Assembly version number
        long_read_sample_id: sample.id of the long-read specimen sample
        hic_sample_id: sample.id of the Hi-C specimen sample (optional)
        sample_metadata_by_id: Sample metadata keyed by sample.id as string (optional)

    Returns:
        Dict representing the manifest (JSON-serialisable)
    """
    logger.info(
        "Generating manifest for organism: %s (taxon_id: %s)",
        organism.scientific_name,
        organism.taxon_id,
    )
    logger.info("Total experiments: %d, Total reads: %d", len(experiments), len(reads))

    long_read_sample_str = str(long_read_sample_id)
    hic_sample_str = str(hic_sample_id) if hic_sample_id else None

    # Build experiment info map: experiment.id → metadata
    exp_info_map: Dict[Any, Dict[str, Any]] = {}
    for exp in experiments:
        exp_info_map[exp.id] = {
            "platform": exp.platform.upper() if exp.platform else "",
            "library_strategy": exp.library_strategy.upper() if exp.library_strategy else "",
            "bpa_package_id": exp.bpa_package_id,
            "bioplatforms_base_url": getattr(exp, "bioplatforms_base_url", None),
            "sample_id": str(exp.sample_id) if getattr(exp, "sample_id", None) else None,
        }

    pacbio_by_package: Dict[str, Any] = {}
    ont_by_package: Dict[str, Any] = {}
    hic_by_package: Dict[str, Any] = {}

    for read in reads:
        if not read.experiment_id:
            logger.debug("Read %s has no experiment_id, skipping", read.id)
            continue

        exp_info = exp_info_map.get(read.experiment_id)
        if not exp_info:
            logger.debug("Read %s has no matching experiment, skipping", read.id)
            continue

        platform = exp_info["platform"]
        library_strategy = exp_info["library_strategy"]
        bpa_package_id = exp_info["bpa_package_id"]
        sample_id = exp_info["sample_id"]
        resolved_sample_id = (
            sequencing_sample_to_specimen_sample_id.get(sample_id, sample_id)
            if sample_id and sequencing_sample_to_specimen_sample_id
            else sample_id
        )
        sample_meta = (
            (sample_metadata_by_id or {}).get(resolved_sample_id, {}) if resolved_sample_id else {}
        )

        # Route by specimen sample, then by platform
        is_long_read_sample = resolved_sample_id == long_read_sample_str
        is_hic_sample = hic_sample_str is not None and resolved_sample_id == hic_sample_str

        if is_long_read_sample:
            if platform == "PACBIO_SMRT" and library_strategy in ("WGS", "WGA") and read.file_name:
                if read.file_name.endswith(".ccs.bam") or read.file_name.endswith("hifi_reads.bam"):
                    logger.info("Adding PacBio read: %s", read.file_name)
                    if bpa_package_id not in pacbio_by_package:
                        entry: Dict[str, Any] = {
                            "sample_id": resolved_sample_id,
                            "bpa_sample_id": sample_meta.get("bpa_sample_id"),
                            "specimen_id": sample_meta.get("specimen_id"),
                            "resources": [],
                        }
                        if exp_info["bioplatforms_base_url"]:
                            entry["bioplatforms_base_url"] = exp_info["bioplatforms_base_url"]
                        pacbio_by_package[bpa_package_id] = entry
                    pacbio_by_package[bpa_package_id]["resources"].append(
                        {"md5sum": read.file_checksum, "url": read.bioplatforms_url}
                    )
                else:
                    logger.debug(
                        "Skipping PacBio read %s — not .ccs.bam or hifi_reads.bam",
                        read.file_name,
                    )
            elif platform == "OXFORD_NANOPORE" and library_strategy in ("WGS", "WGA"):
                logger.info("Adding ONT read: %s", read.file_name)
                if bpa_package_id not in ont_by_package:
                    entry = {
                        "sample_id": resolved_sample_id,
                        "bpa_sample_id": sample_meta.get("bpa_sample_id"),
                        "specimen_id": sample_meta.get("specimen_id"),
                        "resources": [],
                    }
                    if exp_info["bioplatforms_base_url"]:
                        entry["bioplatforms_base_url"] = exp_info["bioplatforms_base_url"]
                    ont_by_package[bpa_package_id] = entry
                ont_by_package[bpa_package_id]["resources"].append(
                    {"md5sum": read.file_checksum, "url": read.bioplatforms_url}
                )

            else:
                logger.debug(
                    "Long-read sample read %s skipped: platform=%s not a long-read platform",
                    read.file_name,
                    platform,
                )

        if is_hic_sample:
            if platform == "ILLUMINA" and library_strategy == "HI-C":
                logger.info(
                    "Adding Hi-C read: %s (library_strategy=%s)", read.file_name, library_strategy
                )
                if bpa_package_id not in hic_by_package:
                    hic_by_package[bpa_package_id] = {
                        "sample_id": resolved_sample_id,
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
                        "Hi-C read %s has unrecognised read_number=%s, skipping",
                        read.file_name,
                        read.read_number,
                    )
            else:
                logger.debug(
                    "Hi-C sample read %s skipped: platform=%s library_strategy=%s not Hi-C",
                    read.file_name,
                    platform,
                    library_strategy,
                )
        elif not is_long_read_sample:
            logger.debug(
                "Read %s sample_id=%s resolved_sample_id=%s does not match either specimen sample, skipping",
                read.id,
                sample_id,
                resolved_sample_id,
            )

    reads_section: Dict[str, Any] = {}
    if pacbio_by_package:
        reads_section["PACBIO_SMRT"] = pacbio_by_package
        logger.info("Added %d PacBio packages to manifest", len(pacbio_by_package))
    if ont_by_package:
        reads_section["OXFORD_NANOPORE"] = ont_by_package
        logger.info("Added %d ONT packages to manifest", len(ont_by_package))
    if hic_by_package:
        reads_section["Hi-C"] = hic_by_package
        logger.info("Added %d Hi-C packages to manifest", len(hic_by_package))

    if not reads_section:
        logger.warning("No reads matched the filtering criteria!")

    return {
        "scientific_name": organism.scientific_name,
        "taxon_id": organism.taxon_id,
        "tolid": tol_id,
        "version": version,
        "reads": reads_section,
    }
