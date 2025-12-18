import uuid
from types import SimpleNamespace
from fastapi.testclient import TestClient

from app.api.v1.endpoints import experiment_submissions
from app.main import app


class _FakeQueryList:
    def __init__(self, data):
        self.data = list(data)
    def filter(self, *_a, **_k):
        return self
    def order_by(self, *_a, **_k):
        return self
    def distinct(self, *_a, **_k):
        return self
    def all(self):
        return list(self.data)
    def first(self):
        return self.data[0] if self.data else None


class _FakeSessionMap:
    def __init__(self, data_map=None):
        self.data_map = data_map or {}
    def query(self, model):
        return _FakeQueryList(self.data_map.get(model, []))


def _override_db(data=None):
    def _gen():
        yield _FakeSessionMap(data)
    return _gen


def test_experiment_submission_by_attr_not_found():
    client = TestClient(app)
    app.dependency_overrides[experiment_submissions.get_current_active_user] = (
        lambda: SimpleNamespace(is_active=True, roles=["admin"], is_superuser=False)
    )
    app.dependency_overrides[experiment_submissions.get_db] = _override_db({})

    resp = client.get("/api/v1/experiment-submissions/by-experiment-attr?bpa_package_id=missing")
    assert resp.status_code == 404


def test_experiment_submission_by_attr_no_submission():
    client = TestClient(app)
    exp_id = uuid.uuid4()
    app.dependency_overrides[experiment_submissions.get_current_active_user] = (
        lambda: SimpleNamespace(is_active=True, roles=["admin"], is_superuser=False)
    )
    app.dependency_overrides[experiment_submissions.get_db] = _override_db(
        {
            experiment_submissions.Experiment: [SimpleNamespace(id=exp_id)],
            experiment_submissions.ExperimentSubmission: [],
        }
    )

    resp = client.get(f"/api/v1/experiment-submissions/by-experiment-attr?experiment_id={exp_id}")
    assert resp.status_code == 404
