from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.endpoints import broker
from app.schemas.broker_contract import (
    BrokerEntityType,
    BrokerReadyClaimRequest,
    BrokerReportRecord,
    BrokerReportRequest,
    BrokerTargetedClaimRequest,
    BrokerValidationRequest,
)
from fastapi import HTTPException


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.flushed = False
        self.executed = []

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
        self.committed = True

    def execute(self, stmt):
        self.executed.append(stmt)


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
        prepared_payload=None,
        accession=None,
    )
    sample_row = SimpleNamespace(
        id=uuid4(),
        sample_id=sample_id,
        status="ready",
        prepared_payload={"alias": "sample-1", "requires_project_accession": True},
        accession=None,
    )
    experiment_row = SimpleNamespace(
        id=uuid4(),
        experiment_id=experiment_id,
        status="ready",
        prepared_payload={"alias": "experiment-1", "requires_study_accession": True},
        sample_accession="SAMEA000001",
        project_accession="PRJ000001",
        accession=None,
    )
    run_row = SimpleNamespace(
        id=uuid4(),
        read_id=run_id,
        status="ready",
        prepared_payload={"alias": "run-1", "file_name": "reads_1.fastq.gz", "file_format": "fastq"},
        experiment_accession="ERX000001",
        accession=None,
    )

    monkeypatch.setattr(broker, "expire_stale_leases", lambda db_arg: {})
    monkeypatch.setattr(
        broker,
        "_get_organism_by_tax_id",
        lambda db_arg, tax_id: SimpleNamespace(grouping_key="org-1"),
    )
    monkeypatch.setattr(broker, "_query_ready_project_submissions", lambda db_arg, tax_id: [project_row])
    monkeypatch.setattr(broker, "_query_ready_sample_submissions", lambda db_arg, tax_id: [sample_row])
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
    assert response.entities[1].prerequisites is None
    assert response.entities[2].prerequisites.sample_accession == "SAMEA000001"
    assert response.entities[2].prerequisites.study_accession == "PRJ000001"
    assert response.entities[3].files[0].filename == "reads_1.fastq.gz"
    assert sample_row.status == "submitting"
    assert db.committed is True


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
        lambda db_arg, entity_type_arg, row_arg, accession_arg: None,
    )

    response = broker.report_submission_outcomes(
        attempt_id=attempt_id,
        payload=BrokerReportRequest(
            attempt_id=attempt_id,
            tax_id=9606,
            results=[
                BrokerReportRecord(
                    attempt_id=attempt_id,
                    entity_type=BrokerEntityType.SAMPLE,
                    entity_id=entity_id,
                    state="completed",
                    accession="SAMEA000001",
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
