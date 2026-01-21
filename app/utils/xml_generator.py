"""
XML generation utilities for ENA submissions.

This module provides functions to generate XML files for various ENA submission types
(samples, experiments, runs, etc.) from the internal JSON representation.
"""

import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.organism import Organism


def generate_sample_xml(
    organism: Organism,
    prepared_payload: Dict[str, Any],
    alias: str,
    center_name: str = "AToL",
    broker_name: str = "AToL",
    accession: Optional[str] = None,
) -> str:
    """
    Generate ENA sample XML from submission JSON data.

    Args:
        prepared_payload: Dictionary containing the sample data in the internal format
        alias: Sample alias (typically the sample ID)
        center_name: Center name for the submission
        broker_name: Broker name for the submission
        accession: Optional accession number if the sample is already registered

    Returns:
        String containing the XML representation of the sample
    """
    # Create root element
    sample_set = ET.Element("SAMPLE_SET")

    # Create sample element with core attributes
    sample = ET.SubElement(sample_set, "SAMPLE")
    sample.set("alias", alias)
    sample.set("center_name", center_name)
    sample.set("broker_name", broker_name)
    if accession:
        sample.set("accession", accession)

    identifiers = ET.SubElement(sample, "IDENTIFIERS")
    if accession:
        primary_id = ET.SubElement(identifiers, "PRIMARY_ID")
        primary_id.text = accession

    submitter_id = ET.SubElement(identifiers, "SUBMITTER_ID")
    submitter_id.set("namespace", center_name)
    submitter_id.text = alias

    title = ET.SubElement(sample, "TITLE")
    title.text = prepared_payload.get("title", f"{alias}")

    sample_name = ET.SubElement(sample, "SAMPLE_NAME")

    taxon_id = ET.SubElement(sample_name, "TAXON_ID")
    taxon_id.text = str(organism.tax_id)

    scientific_name = ET.SubElement(sample_name, "SCIENTIFIC_NAME")
    scientific_name.text = organism.scientific_name

    common_name = ET.SubElement(sample_name, "COMMON_NAME")
    common_name.text = organism.common_name

    if "description" in prepared_payload:
        description = ET.SubElement(sample, "DESCRIPTION")
        description.text = prepared_payload["description"]

    # Add sample attributes
    sample_attributes = ET.SubElement(sample, "SAMPLE_ATTRIBUTES")

    # Skip these keys as they are handled separately
    skip_keys = ["title", "taxon_id", "scientific_name", "common_name", "description", "alias"]

    # Process all other keys as sample attributes
    for key, value in prepared_payload.items():
        if key in skip_keys:
            continue

        if value is None:
            continue

        attribute = ET.SubElement(sample_attributes, "SAMPLE_ATTRIBUTE")

        tag = ET.SubElement(attribute, "TAG")
        tag.text = key

        val = ET.SubElement(attribute, "VALUE")
        val.text = str(value)

        if key == "geographic location (latitude)" or key == "geographic location (longitude)":
            units = ET.SubElement(attribute, "UNITS")
            units.text = "DD"

    # Check if ENA-CHECKLIST exists before adding it in
    checklist_found = any(
        attr.find("TAG").text == "ENA-CHECKLIST"
        for attr in sample_attributes.findall("SAMPLE_ATTRIBUTE")
    )

    if not checklist_found:
        checklist_attr = ET.SubElement(sample_attributes, "SAMPLE_ATTRIBUTE")
        tag = ET.SubElement(checklist_attr, "TAG")
        tag.text = "ENA-CHECKLIST"
        val = ET.SubElement(checklist_attr, "VALUE")
        val.text = "ERC000053"

    # Check project name does not exist before adding it in
    project_name_found = any(
        attr.find("TAG").text == "project name"
        for attr in sample_attributes.findall("SAMPLE_ATTRIBUTE")
    )

    if not project_name_found:
        project_name_attr = ET.SubElement(sample_attributes, "SAMPLE_ATTRIBUTE")
        tag = ET.SubElement(project_name_attr, "TAG")
        tag.text = "project name"
        val = ET.SubElement(project_name_attr, "VALUE")
        val.text = "atol-genome-engine"

    # TO-DO map over mandatory ToL checklist fields and set to "not provided" if they don't yet exist
    # For now, I'm manually adding in a field which doesn't appear in the BPA data:

    # 1. Add collecting institution attribute if not already present
    collecting_institution_found = any(
        attr.find("TAG").text == "collecting institution"
        for attr in sample_attributes.findall("SAMPLE_ATTRIBUTE")
    )

    if not collecting_institution_found:
        collecting_institution_attr = ET.SubElement(sample_attributes, "SAMPLE_ATTRIBUTE")
        tag = ET.SubElement(collecting_institution_attr, "TAG")
        tag.text = "collecting institution"
        val = ET.SubElement(collecting_institution_attr, "VALUE")
        val.text = "not provided"

    rough_string = ET.tostring(sample_set, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="UTF-8").decode("UTF-8")


def generate_experiment_xml(
    prepared_payload: Dict[str, Any],
    alias: str,
    study_accession: Optional[str] = None,
    study_alias: Optional[str] = None,
    sample_accession: Optional[str] = None,
    sample_alias: Optional[str] = None,
    center_name: str = "AToL",
    broker_name: str = "AToL",
    accession: Optional[str] = None,
) -> str:
    """
    Generate ENA experiment XML from submission JSON data.

    Args:
        prepared_payload: Dictionary containing the experiment data in the internal format
        alias: Experiment alias (typically the experiment ID or BPA package ID)
        center_name: Center name for the submission
        broker_name: Broker name for the submission
        accession: Optional accession number if the experiment is already registered

    Returns:
        String containing the XML representation of the experiment
    """
    experiment_set = ET.Element("EXPERIMENT_SET")

    experiment = ET.SubElement(experiment_set, "EXPERIMENT")
    experiment.set("alias", alias)
    experiment.set("center_name", center_name)
    experiment.set("broker_name", broker_name)
    if accession:
        experiment.set("accession", accession)

    identifiers = ET.SubElement(experiment, "IDENTIFIERS")
    if accession:
        primary_id = ET.SubElement(identifiers, "PRIMARY_ID")
        primary_id.text = accession

    submitter_id = ET.SubElement(identifiers, "SUBMITTER_ID")
    submitter_id.set("namespace", center_name)
    submitter_id.text = alias

    title = ET.SubElement(experiment, "TITLE")
    title.text = prepared_payload.get("title", alias)

    study_ref = ET.SubElement(experiment, "STUDY_REF")
    if study_accession:
        study_ref.set("accession", study_accession)
    elif study_alias:
        study_ref.set("refname", study_alias)
    else:
        raise HTTPException(status_code=400, detail="Study accession or refname must be provided")

    design = ET.SubElement(experiment, "DESIGN")

    design_description = ET.SubElement(design, "DESIGN_DESCRIPTION")
    design_description.text = prepared_payload.get("design_description", "")

    sample_descriptor = ET.SubElement(design, "SAMPLE_DESCRIPTOR")
    if sample_accession:
        sample_descriptor.set("accession", sample_accession)
    elif sample_alias:
        sample_descriptor.set("refname", sample_alias)
    else:
        raise HTTPException(status_code=400, detail="Sample accession or refname must be provided")

    library_descriptor = ET.SubElement(design, "LIBRARY_DESCRIPTOR")

    library_name = ET.SubElement(library_descriptor, "LIBRARY_NAME")
    library_name.text = prepared_payload.get("library_name", None)

    library_strategy = ET.SubElement(library_descriptor, "LIBRARY_STRATEGY")
    library_strategy.text = prepared_payload.get("library_strategy", None)

    library_source = ET.SubElement(library_descriptor, "LIBRARY_SOURCE")
    library_source.text = prepared_payload.get("library_source", None)

    library_selection = ET.SubElement(library_descriptor, "LIBRARY_SELECTION")
    library_selection.text = prepared_payload.get("library_selection", None)

    library_construction_protocol = ET.SubElement(
        library_descriptor, "LIBRARY_CONSTRUCTION_PROTOCOL"
    )
    library_construction_protocol.text = prepared_payload.get("library_construction_protocol", None)

    insert_size = ET.SubElement(library_descriptor, "INSERT_SIZE")
    insert_size.text = prepared_payload.get("insert_size", None)

    library_layout = ET.SubElement(library_descriptor, "LIBRARY_LAYOUT")
    layout_type = prepared_payload.get("library_layout", "SINGLE")
    if layout_type == "PAIRED":
        ET.SubElement(library_layout, "PAIRED")
        if "nominal_length" in prepared_payload:
            paired = library_layout.find("PAIRED")
            paired.set("NOMINAL_LENGTH", str(prepared_payload["nominal_length"]))
    else:
        ET.SubElement(library_layout, "SINGLE")  # TODO check if this is correct

    platform = ET.SubElement(experiment, "PLATFORM")
    platform_type = prepared_payload.get("platform", None)
    platform_element = ET.SubElement(platform, platform_type)

    instrument_model = ET.SubElement(platform_element, "INSTRUMENT_MODEL")
    instrument_model.text = prepared_payload.get("instrument_model", None)

    rough_string = ET.tostring(experiment_set, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="UTF-8").decode("UTF-8")


"""
XML generation functions for ENA run submissions.

This module provides utility functions to generate ENA-compliant XML for run submissions.
"""
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from xml.dom import minidom


def _create_run_element(
    prepared_payload: Dict[str, Any],
    alias: str,
    experiment_accession: Optional[str] = None,
    experiment_alias: Optional[str] = None,
    center_name: str = "AToL",
    broker_name: str = "AToL",
    accession: Optional[str] = None,
) -> ET.Element:
    """
    Helper function to create a RUN element with all its children.

    Args:
        prepared_payload: Dictionary containing the run data
        alias: Run alias
        experiment_accession: Optional experiment accession
        experiment_alias: Optional experiment alias/refname
        center_name: Center name
        broker_name: Broker name
        accession: Optional run accession

    Returns:
        XML Element for the RUN
    """
    run = ET.Element("RUN")
    run.set("alias", alias)
    run.set("center_name", center_name)
    run.set("broker_name", broker_name)

    if accession:
        run.set("accession", accession)

    identifiers = ET.SubElement(run, "IDENTIFIERS")

    if accession:
        primary_id = ET.SubElement(identifiers, "PRIMARY_ID")
        primary_id.text = accession

    submitter_id = ET.SubElement(identifiers, "SUBMITTER_ID")
    submitter_id.text = alias
    submitter_id.set("namespace", center_name)

    experiment_ref = ET.SubElement(run, "EXPERIMENT_REF")

    exp_accession = experiment_accession or prepared_payload.get("experiment_accession")
    exp_alias = experiment_alias or prepared_payload.get("experiment_alias")

    if exp_accession:
        experiment_ref.set("accession", exp_accession)
    elif exp_alias:
        experiment_ref.set("refname", exp_alias)
    else:
        # Raise an error if neither experiment_accession nor experiment_alias is provided
        raise HTTPException(
            status_code=400, detail="Experiment accession or alias must be provided"
        )

    data_block = ET.SubElement(run, "DATA_BLOCK")
    files = ET.SubElement(data_block, "FILES")
    file_element = ET.SubElement(files, "FILE")

    if "file_checksum" in prepared_payload:
        file_element.set("checksum", prepared_payload["file_checksum"])
        file_element.set("checksum_method", "MD5")

    if "file_name" in prepared_payload:
        file_element.set("filename", prepared_payload["file_name"])

    if "file_format" in prepared_payload:
        file_element.set("filetype", prepared_payload["file_format"])

    return run


def generate_run_xml(
    prepared_payload: Dict[str, Any],
    alias: str,
    experiment_accession: Optional[str] = None,
    experiment_alias: Optional[str] = None,
    center_name: str = "AToL",
    broker_name: str = "AToL",
    accession: Optional[str] = None,
) -> str:
    """
    Generate ENA run XML from submission JSON data.

    Args:
        prepared_payload: Dictionary containing the run data in the internal format
        alias: Run alias (typically the run ID or BPA dataset ID)
        experiment_accession: Optional experiment accession
        experiment_alias: Optional experiment alias/refname
        center_name: Center name for the submission
        broker_name: Broker name for the submission
        accession: Optional accession number if the run is already registered

    Returns:
        Pretty-printed XML string in ENA run format
    """
    run_set = ET.Element("RUN_SET")

    run = _create_run_element(
        prepared_payload=prepared_payload,
        alias=alias,
        experiment_accession=experiment_accession,
        experiment_alias=experiment_alias,
        center_name=center_name,
        broker_name=broker_name,
        accession=accession,
    )

    run_set.append(run)

    rough_string = ET.tostring(run_set, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="UTF-8").decode("UTF-8")


def generate_runs_xml(
    runs_data: List[Dict[str, Any]],
    experiment_accession: Optional[str] = None,
    experiment_alias: Optional[str] = None,
) -> str:
    """
    Generate ENA run XML for multiple runs.

    Args:
        runs_data: List of dictionaries, each containing:
            - prepared_payload: Dictionary with the run data
            - alias: Run alias
            - accession: Optional accession number
        experiment_accession: Optional experiment accession to override all runs
        experiment_alias: Optional experiment alias/refname to override all runs

    Returns:
        Pretty-printed XML string in ENA run format
    """
    run_set = ET.Element("RUN_SET")

    for run_data in runs_data:
        prepared_payload = run_data["prepared_payload"]
        alias = run_data["alias"]
        accession = run_data.get("accession")
        center_name = run_data.get("center_name", "AToL")
        broker_name = run_data.get("broker_name", "AToL")

        run = _create_run_element(
            prepared_payload=prepared_payload,
            alias=alias,
            experiment_accession=experiment_accession,
            experiment_alias=experiment_alias,
            center_name=center_name,
            broker_name=broker_name,
            accession=accession,
        )

        run_set.append(run)

    rough_string = ET.tostring(run_set, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="UTF-8").decode("UTF-8")
