import os
import xml.etree.ElementTree as ET

import pytest

# Ensure DB URL can be constructed during module import without hitting a real DB
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_SERVER", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "testdb")

import app.core.settings as settings_module

# Explicitly set the settings values before session/engine creation.
settings_module.settings.POSTGRES_USER = "test"
settings_module.settings.POSTGRES_PASSWORD = "test"
settings_module.settings.POSTGRES_SERVER = "localhost"
settings_module.settings.POSTGRES_PORT = "5432"
settings_module.settings.POSTGRES_DB = "testdb"
settings_module.settings.DATABASE_URI = (
    f"postgresql://{settings_module.settings.POSTGRES_USER}:"
    f"{settings_module.settings.POSTGRES_PASSWORD}@"
    f"{settings_module.settings.POSTGRES_SERVER}:"
    f"{settings_module.settings.POSTGRES_PORT}/"
    f"{settings_module.settings.POSTGRES_DB}"
)

from app.utils.xml_generator import generate_experiment_xml, generate_sample_xml


class DummyOrganism:
    def __init__(self):
        self.tax_id = 9606
        self.scientific_name = "Homo sapiens"
        self.common_name = "Human"


def test_generate_sample_xml_includes_required_elements_and_defaults():
    organism = DummyOrganism()
    payload = {
        "title": "Sample Title",
        "description": "Desc",
        "custom_attr": "value",
    }

    xml = generate_sample_xml(organism, payload, alias="S1", accession=None)
    root = ET.fromstring(xml)

    sample = root.find("SAMPLE")
    assert sample is not None
    assert sample.get("alias") == "S1"
    # Core fields
    assert sample.findtext("TITLE") == "Sample Title"
    assert sample.find("DESCRIPTION").text == "Desc"
    assert sample.find("SAMPLE_NAME/TAXON_ID").text == "9606"
    assert sample.find("SAMPLE_NAME/SCIENTIFIC_NAME").text == "Homo sapiens"
    assert sample.find("SAMPLE_NAME/COMMON_NAME").text == "Human"

    attrs = sample.find("SAMPLE_ATTRIBUTES")
    tags = {a.find("TAG").text: a.find("VALUE").text for a in attrs.findall("SAMPLE_ATTRIBUTE")}
    # Custom attribute passed through
    assert tags["custom_attr"] == "value"
    # Defaults auto-added when missing
    assert tags["ENA-CHECKLIST"] == "ERC000053"
    assert tags["project name"] == "atol-genome-engine"
    assert tags["collecting institution"] == "not provided"


def test_generate_experiment_xml_requires_study_and_sample_refs():
    with pytest.raises(Exception):
        generate_experiment_xml({}, alias="EXP1")

    with pytest.raises(Exception):
        generate_experiment_xml({}, alias="EXP1", study_alias="STUDY")

    xml = generate_experiment_xml(
        {"title": "Exp", "design_description": "desc"},
        alias="EXP1",
        study_alias="STUDY",
        sample_alias="SAMPLE",
    )
    root = ET.fromstring(xml)
    experiment = root.find("EXPERIMENT")
    assert experiment.get("alias") == "EXP1"
    assert experiment.find("TITLE").text == "Exp"
    assert experiment.find("DESIGN/DESIGN_DESCRIPTION").text == "desc"
    assert experiment.find("STUDY_REF").get("refname") == "STUDY"
    assert experiment.find("DESIGN/SAMPLE_DESCRIPTOR").get("refname") == "SAMPLE"
