"""Helper functions for assembly operations."""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from app.models.experiment import Experiment
from app.models.organism import Organism
from app.models.read import Read
from app.models.taxonomy_info import TaxonomyInfo
from app.schemas.assembly import AssemblyDataTypes

logger = logging.getLogger(__name__)


def _detect_assembly_data_type_flags(
    experiments: List[Experiment],
) -> Tuple[bool, bool, bool, bool]:
    """Return booleans for PacBio, ONT, and Hi-C using assembly classification rules."""
    has_pacbio = False
    has_nanopore = False
    has_hic = False
    has_rnaseq = False

    for exp in experiments:
        platform = exp.platform.upper() if exp.platform else ""
        library_strategy = exp.library_strategy.upper() if exp.library_strategy else ""

        if platform == "PACBIO_SMRT" and library_strategy in ("WGS", "WGA"):
            has_pacbio = True
        if platform == "OXFORD_NANOPORE" and library_strategy in ("WGS", "WGA"):
            has_nanopore = True
        if platform == "ILLUMINA" and library_strategy == "HI-C":
            has_hic = True
        if platform == "ILLUMINA" and library_strategy == "RNA-SEQ":
            has_rnaseq = True

    return has_pacbio, has_nanopore, has_hic, has_rnaseq


def get_available_assembly_data_types(experiments: List[Experiment]) -> List[str]:
    """Return atomic data types available for a specimen sample.

    This is used by discovery flows, so a sample with only Hi-C data should still
    report ["Hi-C"] even though that combination is not sufficient for creating an
    assembly intent on its own.
    """
    has_pacbio, has_nanopore, has_hic, has_rnaseq = _detect_assembly_data_type_flags(experiments)
    available_data_types: List[str] = []

    if has_pacbio:
        available_data_types.append("PACBIO_SMRT")
    if has_nanopore:
        available_data_types.append("OXFORD_NANOPORE")
    if has_hic:
        available_data_types.append("Hi-C")
    if has_rnaseq:
        available_data_types.append("RNA-Seq")

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
    has_pacbio, has_nanopore, has_hic, has_rnaseq = _detect_assembly_data_type_flags(experiments)

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
    taxonomy_info: Optional[TaxonomyInfo],
    reads: List[Read],
    experiments: List[Experiment],
    tol_id: str | None,
    assembly_id: str,
    version: int,
    long_read_sample_id: UUID,
    hic_sample_ids: Optional[List[UUID]] = None,
    sample_metadata_by_id: Dict[str, Dict[str, Any]] | None = None,
    sequencing_sample_to_specimen_sample_id: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """Generate an assembly manifest as a JSON-serialisable dict.

    Reads are routed to sections based on which specimen sample they belong to:
    - Reads from long_read_sample_id experiments → PACBIO_SMRT or OXFORD_NANOPORE section
    - Reads from hic_sample_ids experiments → Hi-C section (omitted when hic_sample_ids is None)

    PacBio filtering: only files ending in .ccs.bam or hifi_reads.bam are included.
    ONT: all reads are included.
    Hi-C: reads are split into r1/r2 by read_number and include lane_number.

    Args:
        organism: Organism object
        taxonomy_info: TaxonomyInfo object related to the organism when available
        reads: Combined list of Read objects from all specimen samples
        experiments: Combined list of Experiment objects from all specimen samples
        tol_id: ToL ID for the assembly (optional)
        version: Assembly version number
        long_read_sample_id: sample.id of the long-read specimen sample
        hic_sample_ids: sample.ids of the Hi-C specimen samples (optional)
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
    hic_sample_id_strs = {str(sid) for sid in hic_sample_ids} if hic_sample_ids else set()

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
        is_hic_sample = bool(hic_sample_id_strs) and resolved_sample_id in hic_sample_id_strs

        if is_long_read_sample:
            if platform == "PACBIO_SMRT" and library_strategy in ("WGS", "WGA") and read.file_name:
                logger.info("Adding PacBio read: %s", read.file_name)
                if bpa_package_id not in pacbio_by_package:
                    pacbio_by_package[bpa_package_id] = {
                        "sample_id": resolved_sample_id,
                        "bpa_sample_id": sample_meta.get("bpa_sample_id"),
                        "specimen_id": sample_meta.get("specimen_id"),
                        "base_url": exp_info["bioplatforms_base_url"],
                        "single_end": [],
                    }
                pacbio_by_package[bpa_package_id]["single_end"].append(
                    {"md5sum": read.file_checksum, "url": read.bioplatforms_url}
                )
            elif platform == "OXFORD_NANOPORE" and library_strategy in ("WGS", "WGA"):
                logger.info("Adding ONT read: %s", read.file_name)
                if bpa_package_id not in ont_by_package:
                    ont_by_package[bpa_package_id] = {
                        "sample_id": resolved_sample_id,
                        "bpa_sample_id": sample_meta.get("bpa_sample_id"),
                        "specimen_id": sample_meta.get("specimen_id"),
                        "base_url": exp_info["bioplatforms_base_url"],
                        "single_end": [],
                    }
                ont_by_package[bpa_package_id]["single_end"].append(
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
                        "base_url": exp_info["bioplatforms_base_url"],
                        "r1": [],
                        "r2": [],
                    }
                rkey = _normalize_read_number(read.read_number)
                if rkey in ("r1", "r2"):
                    hic_by_package[bpa_package_id][rkey].append(
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

    reads_list: List[Dict[str, Any]] = []
    for pkg_id, entry in pacbio_by_package.items():
        reads_list.append({"data_type": "PACBIO_SMRT", "name": pkg_id, **entry})
    for pkg_id, entry in ont_by_package.items():
        reads_list.append({"data_type": "OXFORD_NANOPORE", "name": pkg_id, **entry})
    for pkg_id, entry in hic_by_package.items():
        reads_list.append({"data_type": "Hi-C", "name": pkg_id, **entry})

    if reads_list:
        logger.info(
            "Manifest read_files: %d PacBio, %d ONT, %d Hi-C packages",
            len(pacbio_by_package),
            len(ont_by_package),
            len(hic_by_package),
        )
    else:
        logger.warning("No reads matched the filtering criteria!")

    manifest = {
        "scientific_name": organism.scientific_name,
        "taxon_id": organism.taxon_id,
        "dataset_id": tol_id,
        "assembly_id": assembly_id,
        "version": version,
        "busco_odb10_dataset_name": getattr(taxonomy_info, "busco_odb10_dataset_name", None),
        "busco_odb12_dataset_name": getattr(taxonomy_info, "busco_odb12_dataset_name", None),
        "find_plastid": getattr(taxonomy_info, "find_plastid", None),
        "hic_motif": getattr(taxonomy_info, "hic_motif", None),
        "mitochondrial_genetic_code_id": getattr(
            taxonomy_info, "mitochondrial_genetic_code_id", None
        ),
        "mitohifi_reference_species": getattr(taxonomy_info, "mitohifi_reference_species", None),
        "oatk_hmm_name": getattr(taxonomy_info, "oatk_hmm_name", None),
        "augustus_dataset_name": getattr(taxonomy_info, "augustus_dataset_name", None),
        "genetic_code_id": getattr(taxonomy_info, "genetic_code_id", None),
        "ncbi_class": getattr(taxonomy_info, "ncbi_class", None),
        "read_files": reads_list,
    }
    return manifest
