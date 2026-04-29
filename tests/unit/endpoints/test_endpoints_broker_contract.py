from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.v1.endpoints import broker
from app.models.experiment import Experiment
from app.models.organism import Organism
from app.models.sample import Sample, SampleSubmission
from app.schemas.broker_contract import (
    BrokerBatchClaimRequest,
    BrokerEntityType,
    BrokerReadyClaimRequest,
    BrokerReportRecord,
    BrokerReportRequest,
    BrokerTargetedClaimRequest,
    BrokerValidationRequest,
)


class FakeQuery:
    """Mock query object for FakeSession."""

    def __init__(self, result=None):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def scalar(self):
        return self._result

    def first(self):
        return self._result


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.flushed = False
        self.rolled_back = False
        self.commit_exception = None
        self.executed = []
        self._accession_lookups = {}  # Map of (entity_type, entity_id) -> accession
        self._query_results = {}  # Map of tuple(query_args) -> scalar/first result

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            try:
                obj.id = uuid4()
            except Exception:
                pass
        self.added.append(obj)

    def flush(self):
        self.flushed = True

    def commit(self):
        if self.commit_exception is not None:
            raise self.commit_exception
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def execute(self, stmt):
        self.executed.append(stmt)

    def query(self, *args):
        """Mock query method that returns configured results by query args."""
        return FakeQuery(result=self._query_results.get(tuple(args), None))


def _broker_user():
    return SimpleNamespace(is_superuser=False, roles=["broker"], is_active=True)


def test_claims_ready_returns_flat_entity_contract(monkeypatch):
    db = FakeSession()
    project_id = uuid4()
    sample_id = uuid4()
    experiment_id = uuid4()
    run_id = uuid4()

    project_row = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        status="ready",
        prepared_payload={"alias": "project-1"},
        accession=None,
        authority="ENA",
    )
    sample_row = SimpleNamespace(
        id=uuid4(),
        sample_id=sample_id,
        project_id=project_id,  # FK to project
        status="ready",
        prepared_payload={
            "alias": "sample-1",
            "requires_project_accession": True,
            "expected_project_accession": "PRJ000001",  # Required but may not exist yet
        },
        accession=None,
        authority="ENA",
    )
    experiment_row = SimpleNamespace(
        id=uuid4(),
        experiment_id=experiment_id,
        sample_id=sample_id,  # FK to sample
        project_id=project_id,  # FK to project
        status="ready",
        prepared_payload={
            "alias": "experiment-1",
            "requires_study_accession": True,
            "expected_study_accession": "PRJ000001",  # Required but not yet submitted
        },
        accession=None,
        authority="ENA",
    )
    run_row = SimpleNamespace(
        id=uuid4(),
        read_id=run_id,
        experiment_id=experiment_id,  # FK to experiment
        project_id=project_id,  # FK to project
        status="ready",
        prepared_payload={
            "alias": "run-1",
            "file_name": "reads_1.fastq.gz",
            "file_format": "fastq",
            "expected_experiment_accession": "ERX000001",  # Required but not submitted
        },
        accession=None,
        authority="ENA",
    )

    monkeypatch.setattr(broker, "expire_stale_leases", lambda db_arg: {})

    db._query_results[(Organism.scientific_name,)] = "Homo sapiens"
    db._query_results[(Experiment.bpa_package_id,)] = "PKG1"
    db._query_results[(Sample.kind, Sample.specimen_id, Sample.bpa_sample_id)] = (
        "specimen",
        "SP1",
        "BPA-S1",
    )
    monkeypatch.setattr(
        broker,
        "_get_organism_by_tax_id",
        lambda db_arg, tax_id: SimpleNamespace(grouping_key="org-1"),
    )
    monkeypatch.setattr(
        broker, "_query_ready_project_submissions", lambda db_arg, tax_id: [project_row]
    )
    monkeypatch.setattr(
        broker, "_query_ready_sample_submissions", lambda db_arg, tax_id: [sample_row]
    )
    monkeypatch.setattr(
        broker, "_query_ready_experiment_submissions", lambda db_arg, tax_id: [experiment_row]
    )
    monkeypatch.setattr(broker, "_query_ready_run_submissions", lambda db_arg, tax_id: [run_row])

    response = broker.claim_ready_entities(
        payload=BrokerReadyClaimRequest(tax_id="9606"),
        current_user=_broker_user(),
        db=db,
    )

    assert response.tax_id == "9606"
    assert response.scope == "full"
    assert [entity.type for entity in response.entities] == [
        BrokerEntityType.PROJECT,
        BrokerEntityType.SAMPLE,
        BrokerEntityType.EXPERIMENT,
        BrokerEntityType.RUN,
    ]

    assert response.entities[0].scientific_name == "Homo sapiens"
    assert response.entities[1].scientific_name == "Homo sapiens"
    assert response.entities[2].scientific_name == "Homo sapiens"
    assert response.entities[3].scientific_name == "Homo sapiens"
    # With normalized lookups, accessions are None unless they exist in accession_registry
    # Projects don't have prerequisite accessions
    assert response.entities[0].prerequisites is None  # No prerequisites for projects

    assert response.entities[1].prerequisites.project_accession is None
    assert response.entities[1].prerequisites.study_accession is None
    assert response.entities[1].payload["title"] == "Specimen SP1 for Homo sapiens"

    assert (
        response.entities[2].prerequisites.sample_accession is None
    )  # Experiment - sample not in registry
    assert response.entities[2].prerequisites.study_accession is None  # Project not in registry
    assert (
        response.entities[2].payload["title"]
        == "Bioplatforms Australia dataset PKG1 for Homo sapiens"
    )

    assert (
        response.entities[3].prerequisites.experiment_accession is None
    )  # Missing experiment accession
    assert response.entities[3].files[0].filename == "reads_1.fastq.gz"
    assert response.entities[3].file_metadata is None
    assert sample_row.status == "submitting"
    assert db.committed is True


def test_report_returns_409_on_integrity_error_during_commit(monkeypatch):
    db = FakeSession()
    attempt_id = uuid4()
    entity_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        sample_id=entity_id,
        attempt_id=attempt_id,
        status="submitting",
        prepared_payload={"alias": "sample-1"},
        authority="ENA",
        accession=None,
        response_payload=None,
        lock_acquired_at=None,
        lock_expires_at=None,
        finalised_attempt_id=None,
        biosample_accession=None,
    )

    monkeypatch.setattr(
        broker,
        "_find_submission_for_attempt",
        lambda db_arg, entity_type_arg, entity_id_arg, attempt_id_arg: row,
    )
    monkeypatch.setattr(broker, "_register_submission_accession", lambda *args, **kwargs: None)

    db.commit_exception = IntegrityError(
        statement="COMMIT",
        params=None,
        orig=Exception("fk_self_accession violation"),
    )

    with pytest.raises(HTTPException) as exc:
        broker.report_submission_outcomes(
            attempt_id=attempt_id,
            payload=BrokerReportRequest(
                results=[
                    BrokerReportRecord(
                        entity_type=BrokerEntityType.SAMPLE,
                        entity_id=entity_id,
                        status="accepted",
                        accession="ERS123456",
                        secondary_accession="SAMEA123456",
                        errors=[],
                    )
                ],
            ),
            current_user=_broker_user(),
            db=db,
        )

    assert exc.value.status_code == 409
    assert "Report failed due to database integrity constraints" in str(exc.value.detail)
    assert db.rolled_back is True


def test_project_entities_never_return_prerequisites_even_if_registry_has_accession(monkeypatch):
    db = FakeSession()
    project_id = uuid4()

    project_row = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        status="ready",
        prepared_payload={"alias": "project-1"},
        accession=None,
        authority="ENA",
    )

    monkeypatch.setattr(broker, "expire_stale_leases", lambda db_arg: {})
    monkeypatch.setattr(
        broker,
        "_find_latest_claimable_entity_submission",
        lambda db_arg, entity_type_arg, entity_id_arg: project_row,
    )
    monkeypatch.setattr(
        broker,
        "_lookup_taxonomy_for_entity",
        lambda db_arg, entity_type_arg, entity_id_arg: ("org-1", 9606),
    )

    # If prerequisites were calculated for projects, we'd see them here.
    # This simulates a (possibly incorrect) accession_registry hit.
    def _fake_prereqs(db_arg, entity_type_arg, prepared_payload_arg, row_arg):
        return broker.BrokerPrerequisites(
            project_accession="PRJEB99999",
            study_accession="PRJEB99999",
        )

    monkeypatch.setattr(broker, "_extract_broker_prerequisites", _fake_prereqs)

    response = broker.claim_batch_entities(
        payload=BrokerBatchClaimRequest(project_ids=[project_id]),
        current_user=_broker_user(),
        db=db,
    )

    assert len(response.entities) == 1
    assert response.entities[0].type == BrokerEntityType.PROJECT
    assert response.entities[0].prerequisites is None


@pytest.mark.parametrize(
    ("entity_type", "row_attr"),
    [
        (BrokerEntityType.PROJECT, "project_id"),
        (BrokerEntityType.SAMPLE, "sample_id"),
        (BrokerEntityType.EXPERIMENT, "experiment_id"),
        (BrokerEntityType.RUN, "read_id"),
    ],
)
def test_claims_entity_returns_requested_entity_only(monkeypatch, entity_type, row_attr):
    db = FakeSession()
    entity_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        status="ready",
        prepared_payload={"alias": f"{entity_type.value}-1"},
        accession=None,
        project_accession=None,
        sample_accession=None,
        experiment_accession=None,
    )
    setattr(row, row_attr, entity_id)

    monkeypatch.setattr(broker, "expire_stale_leases", lambda db_arg: {})
    monkeypatch.setattr(
        broker,
        "_find_latest_claimable_entity_submission",
        lambda db_arg, entity_type_arg, entity_id_arg: row,
    )
    monkeypatch.setattr(
        broker,
        "_lookup_taxonomy_for_entity",
        lambda db_arg, entity_type_arg, entity_id_arg: ("org-1", 9606),
    )

    response = broker.claim_specific_entity(
        payload=BrokerTargetedClaimRequest(entity_type=entity_type, entity_id=entity_id),
        current_user=_broker_user(),
        db=db,
    )

    assert response.tax_id == "9606"
    assert len(response.entities) == 1
    assert response.entities[0].type == entity_type
    assert response.entities[0].id == entity_id
    assert row.status == "submitting"


def test_validation_returns_success_with_override_merge(monkeypatch):
    experiment_id = uuid4()
    row = SimpleNamespace(
        prepared_payload={"alias": "experiment-1"},
        sample_accession=None,
        project_accession=None,
    )

    monkeypatch.setattr(
        broker,
        "_find_latest_submission_for_validation",
        lambda db_arg, entity_type_arg, entity_id_arg: row,
    )
    monkeypatch.setattr(
        broker,
        "_lookup_taxonomy_for_entity",
        lambda db_arg, entity_type_arg, entity_id_arg: ("org-1", 9606),
    )

    response = broker.validate_entity_submission(
        payload=BrokerValidationRequest(
            entity_type=BrokerEntityType.EXPERIMENT,
            entity_id=experiment_id,
            overrides={"sample_accession": "SAMEA000001"},
        ),
        current_user=_broker_user(),
        db=FakeSession(),
    )

    assert response.valid is True
    assert response.issues == []
    assert response.resolved_prerequisites == {"sample_accession": "SAMEA000001"}


def test_validation_returns_failure_when_required_prerequisite_missing(monkeypatch):
    experiment_id = uuid4()
    row = SimpleNamespace(
        prepared_payload={"alias": "experiment-1"},
        sample_accession=None,
        project_accession=None,
    )

    monkeypatch.setattr(
        broker,
        "_find_latest_submission_for_validation",
        lambda db_arg, entity_type_arg, entity_id_arg: row,
    )
    monkeypatch.setattr(
        broker,
        "_lookup_taxonomy_for_entity",
        lambda db_arg, entity_type_arg, entity_id_arg: ("org-1", 9606),
    )

    response = broker.validate_entity_submission(
        payload=BrokerValidationRequest(
            entity_type=BrokerEntityType.EXPERIMENT,
            entity_id=experiment_id,
            overrides={},
        ),
        current_user=_broker_user(),
        db=FakeSession(),
    )

    assert response.valid is False
    assert response.resolved_prerequisites == {}
    assert response.issues[0].field == "sample_accession"


def test_reports_attempt_acceptance(monkeypatch):
    db = FakeSession()
    attempt_id = uuid4()
    entity_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        sample_id=entity_id,
        status="submitting",
        attempt_id=attempt_id,
        authority="ENA",
        accession=None,
        lock_acquired_at=datetime.now(timezone.utc),
        lock_expires_at=datetime.now(timezone.utc),
        finalised_attempt_id=None,
    )

    monkeypatch.setattr(
        broker,
        "_find_submission_for_attempt",
        lambda db_arg, entity_type_arg, entity_id_arg, attempt_id_arg: row,
    )
    monkeypatch.setattr(
        broker,
        "_register_submission_accession",
        lambda db_arg, entity_type_arg, row_arg, accession_arg, secondary_accession=None: None,
    )

    response = broker.report_submission_outcomes(
        attempt_id=attempt_id,
        payload=BrokerReportRequest(
            tax_id=9606,
            results=[
                BrokerReportRecord(
                    entity_type=BrokerEntityType.SAMPLE,
                    entity_id=entity_id,
                    status="completed",
                    accession="ERS000001",
                    secondary_accession="SAMEA000001",
                    receipt_path=None,
                    message=None,
                    errors=[],
                )
            ],
        ),
        current_user=_broker_user(),
        db=db,
    )

    assert response.accepted is True
    assert response.message == "reported"
    assert row.status == "accepted"
    assert row.attempt_id is None


def test_reports_attempt_rejection_creates_new_draft_submission(monkeypatch):
    db = FakeSession()
    attempt_id = uuid4()
    entity_id = uuid4()
    project_id = uuid4()
    prepared_payload = {"alias": "sample-1"}
    row = SimpleNamespace(
        id=uuid4(),
        sample_id=entity_id,
        project_id=project_id,
        status="submitting",
        attempt_id=attempt_id,
        authority="ENA",
        accession=None,
        prepared_payload=prepared_payload,
        response_payload={"receipt_path": None},
        lock_acquired_at=datetime.now(timezone.utc),
        lock_expires_at=datetime.now(timezone.utc),
        finalised_attempt_id=None,
        biosample_accession=None,
    )

    monkeypatch.setattr(
        broker,
        "_find_submission_for_attempt",
        lambda db_arg, entity_type_arg, entity_id_arg, attempt_id_arg: row,
    )
    monkeypatch.setattr(
        broker,
        "_register_submission_accession",
        lambda db_arg, entity_type_arg, row_arg, accession_arg, secondary_accession=None: None,
    )

    response = broker.report_submission_outcomes(
        attempt_id=attempt_id,
        payload=BrokerReportRequest(
            tax_id=9606,
            results=[
                BrokerReportRecord(
                    entity_type=BrokerEntityType.SAMPLE,
                    entity_id=entity_id,
                    status="rejected",
                    receipt_path=None,
                    message="bad",
                    errors=[{"x": "y"}],
                )
            ],
        ),
        current_user=_broker_user(),
        db=db,
    )

    assert response.accepted is True
    assert row.status == "rejected"
    assert row.attempt_id is None

    new_rows = [obj for obj in db.added if isinstance(obj, SampleSubmission)]
    assert len(new_rows) == 1
    new_row = new_rows[0]
    assert new_row.sample_id == entity_id
    assert new_row.project_id == project_id
    assert new_row.status == "draft"
    assert new_row.response_payload is None


def test_claim_ready_entities_no_claimable_entities_returns_empty_response(monkeypatch):
    """Test that when organism exists but has no claimable entities, returns empty response instead of 404."""
    db = FakeSession()

    monkeypatch.setattr(broker, "expire_stale_leases", lambda db_arg: {})
    monkeypatch.setattr(
        broker,
        "_get_organism_by_tax_id",
        lambda db_arg, tax_id: SimpleNamespace(grouping_key="org-1"),
    )
    # Mock all query functions to return empty lists
    monkeypatch.setattr(broker, "_query_ready_project_submissions", lambda db_arg, tax_id: [])
    monkeypatch.setattr(broker, "_query_ready_sample_submissions", lambda db_arg, tax_id: [])
    monkeypatch.setattr(broker, "_query_ready_experiment_submissions", lambda db_arg, tax_id: [])
    monkeypatch.setattr(broker, "_query_ready_run_submissions", lambda db_arg, tax_id: [])

    response = broker.claim_ready_entities(
        payload=BrokerReadyClaimRequest(tax_id="9606"),
        current_user=_broker_user(),
        db=db,
    )

    assert response.tax_id == "9606"
    assert response.scope == "full"
    assert response.entities == []
    assert response.attempt_id is None
    assert db.committed is False  # No commit needed when returning early with empty response


def test_claim_ready_entities_organism_not_found_returns_404(monkeypatch):
    """Test that when organism doesn't exist, returns 404."""
    db = FakeSession()

    monkeypatch.setattr(broker, "expire_stale_leases", lambda db_arg: {})
    monkeypatch.setattr(broker, "_get_organism_by_tax_id", lambda db_arg, tax_id: None)

    with pytest.raises(HTTPException) as exc_info:
        broker.claim_ready_entities(
            payload=BrokerReadyClaimRequest(tax_id="99999"),
            current_user=_broker_user(),
            db=db,
        )

    assert exc_info.value.status_code == 404
    assert "Organism with tax_id 99999 not found" in exc_info.value.detail


def test_claims_batch_single_entity(monkeypatch):
    """Test batch endpoint with a single entity (simplest case)."""
    db = FakeSession()
    sample_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        sample_id=sample_id,
        status="ready",
        prepared_payload={"alias": "sample-1"},
        accession=None,
        project_accession=None,
        sample_accession=None,
        experiment_accession=None,
    )

    monkeypatch.setattr(broker, "expire_stale_leases", lambda db_arg: {})
    monkeypatch.setattr(
        broker,
        "_find_latest_claimable_entity_submission",
        lambda db_arg, entity_type_arg, entity_id_arg: row,
    )
    monkeypatch.setattr(
        broker,
        "_lookup_taxonomy_for_entity",
        lambda db_arg, entity_type_arg, entity_id_arg: ("org-1", 9606),
    )

    response = broker.claim_batch_entities(
        payload=BrokerBatchClaimRequest(sample_ids=[sample_id]),
        current_user=_broker_user(),
        db=db,
    )

    assert response.tax_id == "9606"
    assert len(response.entities) == 1
    assert response.entities[0].type == BrokerEntityType.SAMPLE
    assert response.entities[0].id == sample_id
    assert row.status == "submitting"
    assert db.committed is True


def test_claims_batch_multiple_entities_same_type(monkeypatch):
    """Test batch endpoint with multiple entities of the same type."""
    db = FakeSession()
    sample_id_1 = uuid4()
    sample_id_2 = uuid4()
    sample_id_3 = uuid4()

    rows = {
        sample_id_1: SimpleNamespace(
            id=uuid4(),
            sample_id=sample_id_1,
            status="ready",
            prepared_payload={"alias": "sample-1"},
            accession=None,
            project_accession=None,
            sample_accession=None,
            experiment_accession=None,
        ),
        sample_id_2: SimpleNamespace(
            id=uuid4(),
            sample_id=sample_id_2,
            status="ready",
            prepared_payload={"alias": "sample-2"},
            accession=None,
            project_accession=None,
            sample_accession=None,
            experiment_accession=None,
        ),
        sample_id_3: SimpleNamespace(
            id=uuid4(),
            sample_id=sample_id_3,
            status="ready",
            prepared_payload={"alias": "sample-3"},
            accession=None,
            project_accession=None,
            sample_accession=None,
            experiment_accession=None,
        ),
    }

    def mock_find_submission(db_arg, entity_type_arg, entity_id_arg):
        return rows.get(entity_id_arg)

    monkeypatch.setattr(broker, "expire_stale_leases", lambda db_arg: {})
    monkeypatch.setattr(broker, "_find_latest_claimable_entity_submission", mock_find_submission)
    monkeypatch.setattr(
        broker,
        "_lookup_taxonomy_for_entity",
        lambda db_arg, entity_type_arg, entity_id_arg: ("org-1", 9606),
    )

    response = broker.claim_batch_entities(
        payload=BrokerBatchClaimRequest(sample_ids=[sample_id_1, sample_id_2, sample_id_3]),
        current_user=_broker_user(),
        db=db,
    )

    assert response.tax_id == "9606"
    assert len(response.entities) == 3
    assert all(e.type == BrokerEntityType.SAMPLE for e in response.entities)
    assert {e.id for e in response.entities} == {sample_id_1, sample_id_2, sample_id_3}
    assert all(rows[sid].status == "submitting" for sid in [sample_id_1, sample_id_2, sample_id_3])
    assert db.committed is True


def test_claims_batch_multiple_entity_types(monkeypatch):
    """Test batch endpoint with multiple entity types in one request."""
    db = FakeSession()
    project_id = uuid4()
    sample_id = uuid4()
    experiment_id = uuid4()
    run_id = uuid4()

    rows = {
        (BrokerEntityType.PROJECT, project_id): SimpleNamespace(
            id=uuid4(),
            project_id=project_id,
            status="ready",
            prepared_payload={"alias": "project-1"},
            accession=None,
            project_accession="PRJ000001",
        ),
        (BrokerEntityType.SAMPLE, sample_id): SimpleNamespace(
            id=uuid4(),
            sample_id=sample_id,
            status="ready",
            prepared_payload={"alias": "sample-1"},
            accession=None,
            project_accession=None,
            sample_accession=None,
            experiment_accession=None,
        ),
        (BrokerEntityType.EXPERIMENT, experiment_id): SimpleNamespace(
            id=uuid4(),
            experiment_id=experiment_id,
            status="ready",
            prepared_payload={"alias": "experiment-1"},
            accession=None,
            sample_accession="SAMEA000001",
            project_accession=None,
            experiment_accession=None,
        ),
        (BrokerEntityType.RUN, run_id): SimpleNamespace(
            id=uuid4(),
            read_id=run_id,
            status="ready",
            prepared_payload={
                "alias": "run-1",
                "file_name": "reads.fastq.gz",
                "file_format": "fastq",
            },
            accession=None,
            experiment_accession=None,
        ),
    }

    def mock_find_submission(db_arg, entity_type_arg, entity_id_arg):
        return rows.get((entity_type_arg, entity_id_arg))

    monkeypatch.setattr(broker, "expire_stale_leases", lambda db_arg: {})
    monkeypatch.setattr(broker, "_find_latest_claimable_entity_submission", mock_find_submission)
    monkeypatch.setattr(
        broker,
        "_lookup_taxonomy_for_entity",
        lambda db_arg, entity_type_arg, entity_id_arg: ("org-1", 9606),
    )

    response = broker.claim_batch_entities(
        payload=BrokerBatchClaimRequest(
            project_ids=[project_id],
            sample_ids=[sample_id],
            experiment_ids=[experiment_id],
            run_ids=[run_id],
        ),
        current_user=_broker_user(),
        db=db,
    )

    assert response.tax_id == "9606"
    assert len(response.entities) == 4
    entity_types = [e.type for e in response.entities]
    assert BrokerEntityType.PROJECT in entity_types
    assert BrokerEntityType.SAMPLE in entity_types
    assert BrokerEntityType.EXPERIMENT in entity_types
    assert BrokerEntityType.RUN in entity_types
    assert db.committed is True


def test_claims_batch_multi_organism_returns_null_tax_id(monkeypatch):
    """Test batch endpoint with entities from different organisms returns null tax_id."""
    db = FakeSession()
    sample_id_1 = uuid4()
    sample_id_2 = uuid4()

    rows = {
        sample_id_1: SimpleNamespace(
            id=uuid4(),
            sample_id=sample_id_1,
            status="ready",
            prepared_payload={"alias": "sample-1"},
            accession=None,
            project_accession=None,
            sample_accession=None,
            experiment_accession=None,
        ),
        sample_id_2: SimpleNamespace(
            id=uuid4(),
            sample_id=sample_id_2,
            status="ready",
            prepared_payload={"alias": "sample-2"},
            accession=None,
            project_accession=None,
            sample_accession=None,
            experiment_accession=None,
        ),
    }

    def mock_find_submission(db_arg, entity_type_arg, entity_id_arg):
        return rows.get(entity_id_arg)

    def mock_lookup_taxonomy(db_arg, entity_type_arg, entity_id_arg):
        # Different organisms for different samples
        if entity_id_arg == sample_id_1:
            return ("org-1", 9606)
        else:
            return ("org-2", 9685)

    monkeypatch.setattr(broker, "expire_stale_leases", lambda db_arg: {})
    monkeypatch.setattr(broker, "_find_latest_claimable_entity_submission", mock_find_submission)
    monkeypatch.setattr(broker, "_lookup_taxonomy_for_entity", mock_lookup_taxonomy)

    response = broker.claim_batch_entities(
        payload=BrokerBatchClaimRequest(sample_ids=[sample_id_1, sample_id_2]),
        current_user=_broker_user(),
        db=db,
    )

    assert response.tax_id is None  # Multi-organism batch
    assert len(response.entities) == 2
    assert db.committed is True


def test_claims_batch_empty_request_returns_400(monkeypatch):
    """Test batch endpoint with no entity IDs returns 400."""
    db = FakeSession()

    monkeypatch.setattr(broker, "expire_stale_leases", lambda db_arg: {})

    with pytest.raises(HTTPException) as exc_info:
        broker.claim_batch_entities(
            payload=BrokerBatchClaimRequest(),
            current_user=_broker_user(),
            db=db,
        )

    assert exc_info.value.status_code == 400
    assert "At least one entity ID must be provided" in exc_info.value.detail


def test_claims_batch_entity_not_found_returns_404(monkeypatch):
    """Test batch endpoint with non-existent entity returns 404."""
    db = FakeSession()
    sample_id = uuid4()

    monkeypatch.setattr(broker, "expire_stale_leases", lambda db_arg: {})
    monkeypatch.setattr(
        broker,
        "_find_latest_claimable_entity_submission",
        lambda db_arg, entity_type_arg, entity_id_arg: None,
    )

    with pytest.raises(HTTPException) as exc_info:
        broker.claim_batch_entities(
            payload=BrokerBatchClaimRequest(sample_ids=[sample_id]),
            current_user=_broker_user(),
            db=db,
        )

    assert exc_info.value.status_code == 404
    assert "No claimable submission found" in exc_info.value.detail


def test_claims_batch_entity_without_taxonomy_returns_404(monkeypatch):
    """Test batch endpoint with entity that has no taxonomy returns 404."""
    db = FakeSession()
    sample_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        sample_id=sample_id,
        status="ready",
        prepared_payload={"alias": "sample-1"},
        accession=None,
        project_accession=None,
        sample_accession=None,
        experiment_accession=None,
    )

    monkeypatch.setattr(broker, "expire_stale_leases", lambda db_arg: {})
    monkeypatch.setattr(
        broker,
        "_find_latest_claimable_entity_submission",
        lambda db_arg, entity_type_arg, entity_id_arg: row,
    )
    monkeypatch.setattr(
        broker,
        "_lookup_taxonomy_for_entity",
        lambda db_arg, entity_type_arg, entity_id_arg: (None, None),
    )

    with pytest.raises(HTTPException) as exc_info:
        broker.claim_batch_entities(
            payload=BrokerBatchClaimRequest(sample_ids=[sample_id]),
            current_user=_broker_user(),
            db=db,
        )

    assert exc_info.value.status_code == 404
    assert "Entity not found" in exc_info.value.detail
