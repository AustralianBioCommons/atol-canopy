import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import xml_export
from app.main import app
from app.models.experiment import Experiment, ExperimentSubmission
from app.models.organism import Organism
from app.models.read import Read
from app.models.sample import SampleSubmission


class FakeQueryList:
    def __init__(self, data):
        self.data = list(data)

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.data)

    def first(self):
        return self.data[0] if self.data else None


class FakeSessionMap:
    def __init__(self, data_map=None):
        self.data_map = data_map or {}

    def query(self, model):
        return FakeQueryList(self.data_map.get(model, []))


def override_db(data=None):
    def _gen():
        yield FakeSessionMap(data)

    return _gen


def test_xml_sample_missing_prepared_payload_returns_400():
    client = TestClient(app)
    app.dependency_overrides[xml_export.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )

    sample_id = uuid.uuid4()
    # prepared_payload is None to trigger 400
    ss = SimpleNamespace(
        sample_id=sample_id, prepared_payload=None, organism_id=uuid.uuid4(), sample=None
    )

    app.dependency_overrides[xml_export.get_db] = override_db({SampleSubmission: [ss]})

    resp = client.get(f"/api/v1/xml-export/samples/{sample_id}")
    assert resp.status_code == 400


def test_xml_sample_success():
    client = TestClient(app)
    app.dependency_overrides[xml_export.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )

    sample_id = uuid.uuid4()
    organism_key = "g-1"
    ss = SimpleNamespace(
        sample_id=sample_id,
        prepared_payload={"title": "Sample Title", "alias": "s1"},
        organism_key=organism_key,
        sample=None,
    )
    organism = SimpleNamespace(
        grouping_key=organism_key, tax_id=1, scientific_name="Sci", common_name="Com"
    )

    app.dependency_overrides[xml_export.get_db] = override_db(
        {
            SampleSubmission: [ss],
            Organism: [organism],
        }
    )

    resp = client.get(f"/api/v1/xml-export/samples/{sample_id}")
    assert resp.status_code == 200
    assert "SAMPLE_SET" in resp.text


def test_xml_experiment_by_package_not_found():
    client = TestClient(app)
    app.dependency_overrides[xml_export.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )

    app.dependency_overrides[xml_export.get_db] = override_db({Experiment: []})
    resp = client.get("/api/v1/xml-export/experiments/package/does-not-exist")
    assert resp.status_code == 404


def test_xml_experiment_by_id_missing_prepared_payload_returns_400():
    client = TestClient(app)
    app.dependency_overrides[xml_export.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )

    exp_id = uuid.uuid4()
    es = SimpleNamespace(experiment_id=exp_id, prepared_payload=None, experiment_accession=None)

    app.dependency_overrides[xml_export.get_db] = override_db({ExperimentSubmission: [es]})

    resp = client.get(f"/api/v1/xml-export/experiments/{exp_id}")
    assert resp.status_code == 400


def test_xml_reads_collection_none_have_payload_returns_400():
    client = TestClient(app)
    app.dependency_overrides[xml_export.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )

    # Two reads but both have no prepared_payload
    r1 = SimpleNamespace(id=uuid.uuid4(), prepared_payload=None, bpa_dataset_id="r1")
    r2 = SimpleNamespace(id=uuid.uuid4(), prepared_payload=None, bpa_dataset_id="r2")

    app.dependency_overrides[xml_export.get_db] = override_db({Read: [r1, r2]})

    resp = client.get("/api/v1/xml-export/reads")
    assert resp.status_code == 400


def test_xml_export_read_not_found():
    client = TestClient(app)
    app.dependency_overrides[xml_export.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )

    app.dependency_overrides[xml_export.get_db] = override_db({Read: []})

    resp = client.get(f"/api/v1/xml-export/reads/{uuid.uuid4()}")
    assert resp.status_code == 404
