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


def _make_tolid_row(*, status, taxon_id=1729, specimen_kind="specimen", specimen_id="SPEC-1"):
    sample = Sample(id=uuid4(), taxon_id=taxon_id, kind=specimen_kind, specimen_id=specimen_id)
    row = TolidRequest(
        id=uuid4(),
        sample_id=sample.id,
        tolid_external_id=f"SAMEA-{specimen_id}",
        taxon_id=taxon_id,
        scientific_name=f"Species {taxon_id}",
        status=status,
    )
    row.sample = sample
    return row, sample


def test_requestable_endpoint_only_returns_not_requested_rows_and_specimens():
    requestable_row, _ = _make_tolid_row(status="not_requested", specimen_id="SPEC-1")
    pending_row, _ = _make_tolid_row(status="pending", specimen_id="SPEC-2")
    derived_row, _ = _make_tolid_row(
        status="not_requested",
        specimen_kind="derived",
        specimen_id="SPEC-3",
    )
    db = _Session({TolidRequest: [requestable_row, pending_row, derived_row]})

    out = broker.get_requestable_tolids(
        db=db,
        taxon_id=None,
        sample_id=None,
        sample_ids=None,
        skip=0,
        limit=100,
        current_user=_broker_user(),
    )

    assert [row.sample_id for row in out] == [requestable_row.sample_id]
    assert out[0].status == "not_requested"


def test_pending_endpoint_only_returns_pending_rows_and_supports_taxon_filter():
    first_pending, _ = _make_tolid_row(status="pending", taxon_id=1729, specimen_id="SPEC-1")
    first_pending.last_requested_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    second_pending, _ = _make_tolid_row(status="pending", taxon_id=9999, specimen_id="SPEC-2")
    second_pending.last_requested_at = datetime(2024, 1, 3, tzinfo=timezone.utc)
    requestable_row, _ = _make_tolid_row(status="not_requested", taxon_id=1729, specimen_id="SPEC-3")
    db = _Session({TolidRequest: [first_pending, second_pending, requestable_row]})

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


def test_get_tolid_by_sample_returns_expected_row():
    row, sample = _make_tolid_row(status="pending", specimen_id="SPEC-1")
    row.request_id = "REQ-1"
    row.error_message = "Still waiting"
    db = _Session({TolidRequest: [row], Sample: [sample]})

    out = broker.get_tolid_by_sample(
        sample_id=sample.id,
        db=db,
        current_user=_broker_user(),
    )

    assert out.sample_id == sample.id
    assert out.specimen_id == "SPEC-1"
    assert out.request_id == "REQ-1"
    assert out.error_message == "Still waiting"


def test_report_tolid_result_updates_pending_assigned_and_failed_states():
    sample = Sample(id=uuid4(), taxon_id=1729, kind="specimen", specimen_id="SPEC-1")
    row = TolidRequest(
        id=uuid4(),
        sample_id=sample.id,
        tolid_external_id="SAMEA0001",
        taxon_id=1729,
        scientific_name="Species 1729",
        status="not_requested",
    )
    row.sample = sample
    db = _Session({Sample: [sample], TolidRequest: [row], SampleSubmission: []})

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
    assert pending.status == "pending"
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


def test_report_results_auto_creates_tolid_row_for_accepted_specimen_submission():
    sample = Sample(id=uuid4(), taxon_id=1729, kind="specimen", specimen_id="SPEC-1")
    organism = Organism(taxon_id=1729, scientific_name="Species 1729")
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
                    accession="SAMEA0001",
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
    rows = db.data_map[TolidRequest]
    assert len(rows) == 1
    assert rows[0].sample_id == sample.id
    assert rows[0].tolid_external_id == "SAMEA0001"
    assert rows[0].status == "not_requested"
    assert rows[0].scientific_name == "Species 1729"


def test_report_results_does_not_create_tolid_row_for_non_specimen_sample():
    sample = Sample(id=uuid4(), taxon_id=1729, kind="derived", specimen_id="SPEC-1")
    organism = Organism(taxon_id=1729, scientific_name="Species 1729")
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

    broker.report_results(
        attempt_id=submission.attempt_id,
        payload=broker.ReportRequest(
            attempt_id=submission.attempt_id,
            samples=[
                broker.ReportItem(
                    id=submission.id,
                    status="accepted",
                    accession="SAMEA0001",
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

    assert TolidRequest not in db.data_map
