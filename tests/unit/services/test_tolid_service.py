from datetime import datetime, timezone
from uuid import uuid4

from app.models.organism import Organism
from app.models.sample import Sample, SampleSubmission
from app.models.tolid_request import TolidRequest
from app.schemas.tolid import TolidRequestReport
from app.services.tolid_service import tolid_request_service


class _Query:
    def __init__(self, data):
        self.data = list(data)

    def filter(self, *_a, **_k):
        return self

    def all(self):
        return list(self.data)

    def first(self):
        return self.data[0] if self.data else None


class _Session:
    def __init__(self, data_map):
        self.data_map = data_map
        self.added = []

    def query(self, model):
        return _Query(self.data_map.get(model, []))

    def add(self, obj):
        self.data_map.setdefault(type(obj), [])
        if obj not in self.data_map[type(obj)]:
            self.data_map[type(obj)].append(obj)
        self.added.append(obj)


def test_tolid_request_model_has_expected_indexes():
    table = TolidRequest.__table__
    indexes = {index.name: index for index in table.indexes}

    assert table.name == "tolid_request"
    assert "sample_id" in table.c
    assert indexes["uq_tolid_request_sample_id"].unique is True
    assert "idx_tolid_request_status" in indexes
    assert "idx_tolid_request_status_last_requested_at" in indexes
    assert "idx_tolid_request_request_id" in indexes


def test_get_by_specimen_accession_returns_virtual_not_requested_state_when_row_absent():
    sample_id = uuid4()
    sample = Sample(id=sample_id, taxon_id=1729, kind="specimen", specimen_id="SPEC-1")
    organism = Organism(taxon_id=1729, scientific_name="New name")
    submission = SampleSubmission(
        id=uuid4(),
        sample_id=sample_id,
        status="accepted",
        accession="ERS123456",
        authority="ENA",
        prepared_payload={},
        project_id=uuid4(),
    )
    sample.organism = organism
    db = _Session({Sample: [sample], SampleSubmission: [submission], Organism: [organism]})

    out = tolid_request_service.get_by_specimen_accession(db, "ERS123456")

    assert out.sample_id == sample_id
    assert out.specimen_id == "ERS123456"
    assert out.status == "not_requested"
    assert out.scientific_name == "New name"
    assert out.kind == "specimen"


def test_report_result_creates_row_lazily_and_updates_sample_tolid():
    sample = Sample(id=uuid4(), taxon_id=1729, kind="specimen", specimen_id="SPEC-1")
    organism = Organism(taxon_id=1729, scientific_name="Species name")
    submission = SampleSubmission(
        id=uuid4(),
        sample_id=sample.id,
        status="accepted",
        accession="ERS123456",
        authority="ENA",
        prepared_payload={},
        project_id=uuid4(),
        submitted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    sample.organism = organism
    db = _Session({Sample: [sample], SampleSubmission: [submission], Organism: [organism]})

    view = tolid_request_service.report_result(
        db,
        sample_id=sample.id,
        report=TolidRequestReport(
            status="assigned",
            tolid="tol123",
            request_id="REQ-1",
            last_requested_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        ),
    )

    row = db.data_map[TolidRequest][0]
    assert row.status == "assigned"
    assert row.tolid == "tol123"
    assert row.tolid_external_id == "ERS123456"
    assert sample.tolid == "tol123"
    assert view.tolid == "tol123"
    assert view.specimen_id == "ERS123456"
