import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import experiment_reads_xml


class _FakeQuery:
    def filter(self, *_a, **_k):
        return self

    def all(self):
        return []


class _FakeSession:
    def query(self, _model):
        return _FakeQuery()


def test_experiment_reads_xml_not_found():
    with pytest.raises(HTTPException) as exc:
        experiment_reads_xml.get_experiment_reads_xml(
            db=_FakeSession(),
            experiment_id=uuid.uuid4(),
            current_user=SimpleNamespace(),
        )
    assert exc.value.status_code == 404
