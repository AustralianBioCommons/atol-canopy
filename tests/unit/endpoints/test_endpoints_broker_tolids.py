from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.api.v1.endpoints import broker
from app.models.organism import Organism
from app.models.sample import Sample, SampleSubmission
from app.models.tolid_request import TolidRequest
from app.schemas.tolid import TolidRequestReport


def _broker_user():
    return SimpleNamespace(is_superuser=False, roles=["broker"], is_active=True)


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
    def __init__(self, data_map=None):
        self.data_map = data_map or {}
        self.added = []
        self.committed = False
        self.flushed = False
        self.executed = []

    def query(self, model):
        return _Query(self.data_map.get(model, []))

    def add(self, obj):
        self.data_map.setdefault(type(obj), [])
        if obj not in self.data_map[type(obj)]:
            self.data_map[type(obj)].append(obj)
        self.added.append(obj)

    def flush(self):
        self.flushed = True

    def commit(self):
        self.committed = True

    def execute(self, stmt):
        self.executed.append(stmt)


def _make_tolid_row(*, status, accession, taxon_id=1729, specimen_kind="specimen"):
    sample = Sample(id=uuid4(), taxon_id=taxon_id, kind=specimen_kind, specimen_id="CANOPY-SPEC-1")
    organism = Organism(taxon_id=taxon_id, scientific_name=f"Species {taxon_id}")
    sample.organism = organism
    row = TolidRequest(
        id=uuid4(),
        sample_id=sample.id,
        tolid_external_id=accession,
        taxon_id=taxon_id,
        scientific_name=f"Species {taxon_id}",
        status=status,
    )
    row.sample = sample
    submission = SampleSubmission(
        id=uuid4(),
        sample_id=sample.id,
        status="accepted",
        accession=accession,
        authority="ENA",
        prepared_payload={},
        project_id=uuid4(),
    )
    return row, sample, submission, organism


def test_lookup_by_specimen_accession_returns_virtual_not_requested_state_without_row():
    sample = Sample(id=uuid4(), taxon_id=1729, kind="specimen", specimen_id="CANOPY-SPEC-1")
    organism = Organism(taxon_id=1729, scientific_name="Species 1729")
    sample.organism = organism
    submission = SampleSubmission(
        id=uuid4(),
        sample_id=sample.id,
        status="accepted",
        accession="ERS123456",
        authority="ENA",
        prepared_payload={},
        project_id=uuid4(),
    )
    db = _Session({Sample: [sample], SampleSubmission: [submission], Organism: [organism]})

    out = broker.get_tolid_by_specimen_accession(
        specimen_id="ERS123456",
        db=db,
        current_user=_broker_user(),
    )

    assert out.sample_id == sample.id
    assert out.specimen_id == "ERS123456"
    assert out.status == "not_requested"
    assert out.kind == "specimen"
    assert out.sample_payload["specimen_id"] == "CANOPY-SPEC-1"


def test_lookup_by_specimen_accession_returns_existing_tolid_state():
    row, sample, submission, organism = _make_tolid_row(status="pending", accession="ERS123456")
    row.request_id = "REQ-1"
    row.error_message = "Still waiting"
    db = _Session(
        {
            TolidRequest: [row],
            Sample: [sample],
            SampleSubmission: [submission],
            Organism: [organism],
        }
    )

    out = broker.get_tolid_by_specimen_accession(
        specimen_id="ERS123456",
        db=db,
        current_user=_broker_user(),
    )

    assert out.sample_id == sample.id
    assert out.specimen_id == "ERS123456"
    assert out.request_id == "REQ-1"
    assert out.error_message == "Still waiting"


def test_pending_endpoint_only_returns_pending_rows_and_supports_taxon_filter():
    first_pending, sample_1, submission_1, organism_1 = _make_tolid_row(
        status="pending",
        accession="ERS123456",
        taxon_id=1729,
    )
    first_pending.last_requested_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    second_pending, sample_2, submission_2, organism_2 = _make_tolid_row(
        status="pending",
        accession="ERS999999",
        taxon_id=9999,
    )
    second_pending.last_requested_at = datetime(2024, 1, 3, tzinfo=timezone.utc)
    assigned_row, sample_3, submission_3, organism_3 = _make_tolid_row(
        status="assigned",
        accession="ERS000000",
        taxon_id=1729,
    )
    db = _Session(
        {
            TolidRequest: [first_pending, second_pending, assigned_row],
            Sample: [sample_1, sample_2, sample_3],
            SampleSubmission: [submission_1, submission_2, submission_3],
            Organism: [organism_1, organism_2, organism_3],
        }
    )

    out = broker.get_pending_tolids(
        db=db,
        taxon_id=1729,
        sample_id=None,
        sample_ids=None,
        requested_before=datetime(2024, 1, 2, tzinfo=timezone.utc),
        skip=0,
        limit=100,
        current_user=_broker_user(),
    )

    assert [row.sample_id for row in out] == [first_pending.sample_id]
    assert out[0].status == "pending"
    assert out[0].specimen_id == "ERS123456"


def test_get_tolid_by_sample_returns_virtual_state_using_accession():
    sample = Sample(id=uuid4(), taxon_id=1729, kind="specimen", specimen_id="CANOPY-SPEC-1")
    organism = Organism(taxon_id=1729, scientific_name="Species 1729")
    sample.organism = organism
    submission = SampleSubmission(
        id=uuid4(),
        sample_id=sample.id,
        status="accepted",
        accession="ERS123456",
        authority="ENA",
        prepared_payload={},
        project_id=uuid4(),
    )
    db = _Session({Sample: [sample], SampleSubmission: [submission], Organism: [organism]})

    out = broker.get_tolid_by_sample(
        sample_id=sample.id,
        db=db,
        current_user=_broker_user(),
    )

    assert out.sample_id == sample.id
    assert out.specimen_id == "ERS123456"
    assert out.status == "not_requested"


def test_report_tolid_result_creates_row_lazily_and_updates_states():
    sample = Sample(id=uuid4(), taxon_id=1729, kind="specimen", specimen_id="CANOPY-SPEC-1")
    organism = Organism(taxon_id=1729, scientific_name="Species 1729")
    sample.organism = organism
    submission = SampleSubmission(
        id=uuid4(),
        sample_id=sample.id,
        status="accepted",
        accession="ERS123456",
        authority="ENA",
        prepared_payload={},
        project_id=uuid4(),
    )
    db = _Session({Sample: [sample], SampleSubmission: [submission], Organism: [organism]})

    pending = broker.report_tolid_result(
        sample_id=sample.id,
        payload=TolidRequestReport(
            status="pending",
            request_id="REQ-1",
            last_requested_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
        db=db,
        current_user=_broker_user(),
    )
    row = db.data_map[TolidRequest][0]
    assert pending.status == "pending"
    assert pending.specimen_id == "ERS123456"
    assert row.request_id == "REQ-1"

    assigned = broker.report_tolid_result(
        sample_id=sample.id,
        payload=TolidRequestReport(
            status="assigned",
            tolid="tol123",
            request_id="REQ-1",
            last_requested_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        ),
        db=db,
        current_user=_broker_user(),
    )
    assert assigned.status == "assigned"
    assert row.tolid == "tol123"
    assert sample.tolid == "tol123"

    failed = broker.report_tolid_result(
        sample_id=sample.id,
        payload=TolidRequestReport(
            status="failed",
            request_id="REQ-2",
            error_message="remote error",
            last_requested_at=datetime(2024, 1, 3, tzinfo=timezone.utc),
        ),
        db=db,
        current_user=_broker_user(),
    )
    assert failed.status == "failed"
    assert row.error_message == "remote error"
    assert db.committed is True


def test_report_results_does_not_auto_create_tolid_row_for_accepted_specimen_submission():
    sample = Sample(id=uuid4(), taxon_id=1729, kind="specimen", specimen_id="CANOPY-SPEC-1")
    organism = Organism(taxon_id=1729, scientific_name="Species 1729")
    sample.organism = organism
    submission = SampleSubmission(
        id=uuid4(),
        sample_id=sample.id,
        status="submitting",
        attempt_id=uuid4(),
        authority="ENA",
        prepared_payload={},
        project_id=uuid4(),
    )
    db = _Session({SampleSubmission: [submission], Sample: [sample], Organism: [organism]})

    result = broker.report_results(
        attempt_id=submission.attempt_id,
        payload=broker.ReportRequest(
            attempt_id=submission.attempt_id,
            samples=[
                broker.ReportItem(
                    id=submission.id,
                    status="accepted",
                    accession="ERS123456",
                    submitted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                )
            ],
            experiments=[],
            reads=[],
            projects=[],
        ),
        db=db,
        current_user=_broker_user(),
    )

    assert result.updated_counts["samples"] == 1
    assert TolidRequest not in db.data_map
