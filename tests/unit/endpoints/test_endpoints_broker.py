from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import broker
from app.models.broker import SubmissionAttempt
from app.models.experiment import ExperimentSubmission
from app.models.organism import Organism
from app.models.project import ProjectSubmission
from app.models.read import ReadSubmission
from app.models.sample import SampleSubmission


class FakeQuery:
    def __init__(self, items):
        self.items = list(items)

    def filter(self, *_, **__):
        return self

    def with_for_update(self, *_, **__):
        return self

    def join(self, *_, **__):
        return self

    def all(self):
        return list(self.items)

    def first(self):
        return self.items[0] if self.items else None

    def limit(self, *_):
        return self

    def offset(self, *_):
        return self

    def order_by(self, *_):
        return self

    def count(self):
        return len(self.items)

    def group_by(self, *_):
        return self


class FakeSession:
    def __init__(self, mapping=None):
        self.mapping = mapping or {}
        self.added = []
        self.executed = []
        self.committed = False
        self.flushed = False

    def query(self, model):
        return FakeQuery(self.mapping.get(model, []))

    def add(self, obj):
        # Ensure IDs exist for rows that expect them
        if getattr(obj, "id", None) is None:
            try:
                obj.id = uuid4()
            except Exception:
                pass
        self.added.append(obj)

    def flush(self):
        self.flushed = True

    def commit(self):
        self.committed = True

    def delete(self, obj):
        self.added.append(obj)

    def execute(self, stmt):
        self.executed.append(stmt)


def test_broker_claim_explicit_ids_empty_lists_returns_empty_response():
    broker_user = SimpleNamespace(is_superuser=False, roles=["broker"])
    db = FakeSession(
        {
            Organism: [
                SimpleNamespace(
                    grouping_key="g1",
                    scientific_name="Sci",
                    tax_id=1,
                    bpa_json={"culture_or_strain_id": "C1"},
                )
            ]
        }
    )
    payload = broker.ClaimRequest(
        sample_submission_ids=[uuid4()],
        experiment_submission_ids=[uuid4()],
        read_submission_ids=[uuid4()],
        project_submission_ids=[uuid4()],
        lease_duration_minutes=5,
    )

    with pytest.raises(HTTPException) as excinfo:
        broker.claim_drafts_for_organism(
            organism_key="g1",
            per_type_limit=10,
            payload=payload,
            current_user=broker_user,
            db=db,
        )

    assert excinfo.value.status_code == 400


def test_broker_renew_attempt_lease_updates_items():
    att_id = uuid4()
    attempt = SimpleNamespace(id=att_id, lock_expires_at=None)

    s1 = SimpleNamespace(id=uuid4(), attempt_id=att_id, status="submitting", lock_expires_at=None)
    e1 = SimpleNamespace(id=uuid4(), attempt_id=att_id, status="submitting", lock_expires_at=None)
    r1 = SimpleNamespace(id=uuid4(), attempt_id=att_id, status="submitting", lock_expires_at=None)
    p1 = SimpleNamespace(id=uuid4(), attempt_id=att_id, status="submitting", lock_expires_at=None)

    db = FakeSession(
        {
            SubmissionAttempt: [attempt],
            SampleSubmission: [s1],
            ExperimentSubmission: [e1],
            ReadSubmission: [r1],
            ProjectSubmission: [p1],
        }
    )

    out = broker.renew_attempt_lease(attempt_id=att_id, extend_minutes=5, db=db)
    assert out["attempt_id"] == str(att_id)
    # Ensure locks were set
    assert s1.lock_expires_at is not None
    assert e1.lock_expires_at is not None
    assert r1.lock_expires_at is not None
    assert p1.lock_expires_at is not None


def test_broker_finalise_attempt_releases_items():
    att_id = uuid4()
    attempt = SimpleNamespace(id=att_id, status="processing")

    def mk(kind):
        return SimpleNamespace(
            id=uuid4(),
            attempt_id=att_id,
            status="submitting",
            lock_acquired_at=datetime.now(timezone.utc),
            lock_expires_at=datetime.now(timezone.utc),
        )

    s1, e1, r1, p1 = mk("s"), mk("e"), mk("r"), mk("p")

    db = FakeSession(
        {
            SubmissionAttempt: [attempt],
            SampleSubmission: [s1],
            ExperimentSubmission: [e1],
            ReadSubmission: [r1],
            ProjectSubmission: [p1],
        }
    )

    out = broker.finalise_attempt(attempt_id=att_id, db=db)
    assert out["attempt_id"] == str(att_id)
    assert out["released"] == {"samples": 1, "experiments": 1, "reads": 1, "projects": 1}
    # Items should be reset to draft and cleared lease
    for item in (s1, e1, r1, p1):
        assert item.status == "draft"
        assert item.attempt_id is None
        assert item.lock_acquired_at is None
        assert item.lock_expires_at is None


def test_broker_report_results_sample_accepted():
    att_id = uuid4()
    sub_id = uuid4()

    sub = SimpleNamespace(
        id=sub_id,
        sample_id=uuid4(),
        status="submitting",
        attempt_id=att_id,
        authority="ENA",
        prepared_payload={},
    )
    db = FakeSession({SampleSubmission: [sub]})

    payload = broker.ReportRequest(
        attempt_id=att_id,
        samples=[
            broker.ReportItem(
                id=sub_id,
                status="accepted",
                accession="SAM1",
                submitted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
        ],
        experiments=[],
        reads=[],
        projects=[],
    )

    result = broker.report_results(attempt_id=att_id, payload=payload, db=db)
    assert result.updated_counts["samples"] == 1
    assert sub.status == "accepted"
    assert sub.attempt_id is None
    assert getattr(sub, "finalised_attempt_id", None) == att_id


def test_broker_list_attempts_basic(monkeypatch):
    a1 = SimpleNamespace(
        id=uuid4(),
        organism_key="g1",
        campaign_label=None,
        lock_expires_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    a2 = SimpleNamespace(
        id=uuid4(),
        organism_key="g2",
        campaign_label="c2",
        lock_expires_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db = FakeSession({SubmissionAttempt: [a1, a2]})

    def fake_counts(db_arg, attempt_id):
        return {
            "samples": {"accepted": 1, "draft": 0, "submitting": 0, "rejected": 0},
            "experiments": {"accepted": 0, "draft": 0, "submitting": 0, "rejected": 0},
            "reads": {"accepted": 0, "draft": 0, "submitting": 0, "rejected": 0},
            "projects": {"accepted": 0, "draft": 0, "submitting": 0, "rejected": 0},
        }

    monkeypatch.setattr(broker, "_counts_by_entity_for_attempt", fake_counts)
    monkeypatch.setattr(broker, "_derive_attempt_status", lambda counts, lock: "active")

    out = broker.list_attempts(db=db, page=1, page_size=10)
    assert out["total"] == 2
    assert len(out["items"]) == 2
    assert out["items"][0]["organism_key"] in {"g1", "g2"}


def test_broker_get_attempt_include_items(monkeypatch):
    att = SimpleNamespace(
        id=uuid4(),
        organism_key="g1",
        campaign_label=None,
        lock_expires_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db = FakeSession({SubmissionAttempt: [att]})
    monkeypatch.setattr(
        broker,
        "_counts_by_entity_for_attempt",
        lambda db_arg, attempt_id: {"samples": {}, "experiments": {}, "reads": {}, "projects": {}},
    )
    monkeypatch.setattr(broker, "_derive_attempt_status", lambda counts, lock: "idle")
    items = {
        "samples": [broker.ClaimedEntity(id=uuid4())],
        "experiments": [],
        "reads": [],
        "projects": [],
    }
    monkeypatch.setattr(
        broker, "_get_attempt_items_with_relationships", lambda db_arg, attempt_id: items
    )
    out = broker.get_attempt(attempt_id=att.id, db=db, include_items=True)
    assert out["attempt_id"] == str(att.id)
    assert (
        "items" in out and "samples" in out["items"] and isinstance(out["items"]["samples"], list)
    )


def test_broker_get_attempt_not_found():
    db = FakeSession({SubmissionAttempt: []})
    with pytest.raises(HTTPException) as exc:
        broker.get_attempt(attempt_id=uuid4(), db=db, include_items=False)
    assert exc.value.status_code == 404


def test_broker_get_attempt_items_serialised(monkeypatch):
    att_id = uuid4()
    db = FakeSession({})
    items = {
        "samples": [broker.ClaimedEntity(id=uuid4())],
        "experiments": [],
        "reads": [],
        "projects": [],
    }
    monkeypatch.setattr(
        broker, "_get_attempt_items_with_relationships", lambda db_arg, attempt_id: items
    )
    out = broker.get_attempt_items(attempt_id=att_id, db=db)
    assert set(out.keys()) == {"samples", "experiments", "reads", "projects"}
    assert isinstance(out["samples"], list)


def test_broker_organism_summary(monkeypatch):
    # Prepare attempts and summary counts
    att = SimpleNamespace(
        id=uuid4(),
        organism_key="g1",
        lock_expires_at=datetime.now() + timedelta(minutes=10),
        created_at=datetime.now(),
    )

    class _SummarySession(FakeSession):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def query(self, model, *args, **kwargs):
            self.calls += 1
            # 1st call: attempts (latest)
            if model is SubmissionAttempt and self.calls == 1:
                return FakeQuery([att])
            # 2nd: sample counts rows
            if self.calls == 2:
                return FakeQuery([("draft", 2), ("accepted", 1)])
            # 3rd: experiment counts rows
            if self.calls == 3:
                return FakeQuery([("draft", 0), ("accepted", 3)])
            # 4th: read counts rows
            if self.calls == 4:
                return FakeQuery([("draft", 1), ("accepted", 0)])
            # 5th: attempts for active
            if model is SubmissionAttempt and self.calls == 5:
                return FakeQuery([att])
            return FakeQuery([])

    db = _SummarySession()
    monkeypatch.setattr(
        broker,
        "_counts_by_entity_for_attempt",
        lambda db_arg, attempt_id: {"samples": {"submitting": 1}},
    )
    monkeypatch.setattr(broker, "_derive_attempt_status", lambda counts, lock: "active")

    out = broker.organism_summary(organism_key="g1", db=db, recent_attempts=1)
    assert out["organism_key"] == "g1"
    assert len(out["latest_attempts"]) == 1
    assert "counts_by_entity" in out and set(out["counts_by_entity"].keys()) == {
        "samples",
        "experiments",
        "reads",
    }


def test_broker_renew_attempt_lease_not_found():
    db = FakeSession({SubmissionAttempt: []})
    with pytest.raises(HTTPException) as exc:
        broker.renew_attempt_lease(attempt_id=uuid4(), extend_minutes=5, db=db)
    assert exc.value.status_code == 404


def test_broker_finalise_attempt_not_found():
    db = FakeSession({SubmissionAttempt: []})
    with pytest.raises(HTTPException) as exc:
        broker.finalise_attempt(attempt_id=uuid4(), db=db)
    assert exc.value.status_code == 404


def test_broker_report_results_sample_status_conflict():
    att_id = uuid4()
    sub_id = uuid4()
    sub = SimpleNamespace(id=sub_id, sample_id=uuid4(), status="draft", attempt_id=att_id)
    db = FakeSession({SampleSubmission: [sub]})
    payload = broker.ReportRequest(
        attempt_id=att_id,
        samples=[broker.ReportItem(id=sub_id, status="accepted")],
        experiments=[],
        reads=[],
        projects=[],
    )
    with pytest.raises(HTTPException) as exc:
        broker.report_results(attempt_id=att_id, payload=payload, db=db)
    assert exc.value.status_code == 409


def test_broker_report_results_sample_attempt_mismatch():
    att_id = uuid4()
    sub_id = uuid4()
    sub = SimpleNamespace(id=sub_id, sample_id=uuid4(), status="submitting", attempt_id=uuid4())
    db = FakeSession({SampleSubmission: [sub]})
    payload = broker.ReportRequest(
        attempt_id=att_id,
        samples=[broker.ReportItem(id=sub_id, status="accepted")],
        experiments=[],
        reads=[],
        projects=[],
    )
    with pytest.raises(HTTPException) as exc:
        broker.report_results(attempt_id=att_id, payload=payload, db=db)
    assert exc.value.status_code == 409


def test_broker_report_results_experiment_registry_inserts_and_accept():
    att_id = uuid4()
    sub_id = uuid4()
    exp_id = uuid4()
    sample_id = uuid4()
    sub = SimpleNamespace(
        id=sub_id,
        experiment_id=exp_id,
        sample_id=sample_id,
        status="submitting",
        attempt_id=att_id,
        authority="ENA",
    )
    db = FakeSession({ExperimentSubmission: [sub]})
    payload = broker.ReportRequest(
        attempt_id=att_id,
        samples=[],
        experiments=[
            broker.ReportItem(
                id=sub_id,
                status="accepted",
                accession="EXP1",
                sample_accession="SAM1",
                submitted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
        ],
        reads=[],
        projects=[],
    )
    result = broker.report_results(attempt_id=att_id, payload=payload, db=db)
    assert result.updated_counts["experiments"] == 1
    # Expect at least two registry inserts (sample accession + experiment accession)
    assert len(db.executed) >= 2


def test_broker_report_results_read_registry_inserts_and_accept():
    att_id = uuid4()
    sub_id = uuid4()
    read_id = uuid4()
    exp_id = uuid4()
    sub = SimpleNamespace(
        id=sub_id,
        read_id=read_id,
        experiment_id=exp_id,
        status="submitting",
        attempt_id=att_id,
        authority="ENA",
    )
    db = FakeSession({ReadSubmission: [sub]})
    payload = broker.ReportRequest(
        attempt_id=att_id,
        samples=[],
        experiments=[],
        reads=[
            broker.ReportItem(
                id=sub_id,
                status="accepted",
                accession="RUN1",
                experiment_accession="EXP1",
                submitted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
        ],
        projects=[],
    )
    result = broker.report_results(attempt_id=att_id, payload=payload, db=db)
    assert result.updated_counts["reads"] == 1
    # Expect at least two registry inserts (experiment accession + run accession)
    assert len(db.executed) >= 2


def test_broker_report_results_project_rejected_clears_lease():
    att_id = uuid4()
    sub_id = uuid4()
    proj_id = uuid4()
    sub = SimpleNamespace(
        id=sub_id, project_id=proj_id, status="submitting", attempt_id=att_id, authority="ENA"
    )
    db = FakeSession({ProjectSubmission: [sub]})
    payload = broker.ReportRequest(
        attempt_id=att_id,
        samples=[],
        experiments=[],
        reads=[],
        projects=[
            broker.ReportItem(
                id=sub_id, status="rejected", submitted_at=datetime(2024, 1, 1, tzinfo=timezone.utc)
            )
        ],
    )
    result = broker.report_results(attempt_id=att_id, payload=payload, db=db)
    assert result.updated_counts["projects"] == 1
    assert sub.attempt_id is None
    assert getattr(sub, "finalised_attempt_id", None) == att_id
