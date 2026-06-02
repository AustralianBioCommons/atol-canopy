import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import qc_reads
from app.main import app
from app.models.qc_read import QcRead, QcReadFile, QcReadSubmission
from app.models.read import Read


def _override_db(fake):
    def _gen():
        yield fake

    return _gen


class _QuerySingle:
    def __init__(self, obj):
        self.obj = obj

    def filter(self, *_a, **_k):
        return self

    def join(self, *_a, **_k):
        return self

    def first(self):
        return self.obj


class _SessionQcReport:
    def __init__(self, read_obj=None):
        self.read_obj = read_obj
        self.qc_read = None
        self.qc_files = []
        self.submissions = []

    def query(self, model):
        if model is Read:
            return _QuerySingle(self.read_obj)
        return _QuerySingle(None)

    def add(self, obj):
        now = datetime.now(timezone.utc)
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now

        if isinstance(obj, QcRead):
            obj.files = []
            obj.submission_records = []
            self.qc_read = obj
        elif isinstance(obj, QcReadFile):
            self.qc_files.append(obj)
            if self.qc_read is not None:
                self.qc_read.files.append(obj)
        elif isinstance(obj, QcReadSubmission):
            self.submissions.append(obj)
            if self.qc_read is not None:
                self.qc_read.submission_records.append(obj)

    def flush(self):
        pass

    def commit(self):
        pass

    def refresh(self, obj):
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def test_report_qc_result_creates_paired_fastq_qc_read():
    client = TestClient(app)
    read_obj = Read(
        id=uuid.uuid4(),
        experiment_id=uuid.uuid4(),
        bpa_resource_id="res-1",
        file_name="input.fastq.gz",
        file_format="fastq",
    )
    fake_db = _SessionQcReport(read_obj=read_obj)
    app.dependency_overrides[qc_reads.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["genome_launcher"], is_superuser=False
    )
    app.dependency_overrides[qc_reads.get_db] = _override_db(fake_db)

    try:
        resp = client.post(
            f"/api/v1/qc-reads/{read_obj.id}/report",
            json={
                "base_count": 150,
                "read_count": 10,
                "qc_bases_removed": 5,
                "qc_reads_removed": 1,
                "mean_gc_content": 42.3,
                "n50_length": 500,
                "checksums": {
                    "qc/sample_R1.fastq.gz": {
                        "md5": "d41d8cd98f00b204e9800998ecf8427e",
                        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    },
                    "qc/sample_R2.fastq.gz": {
                        "md5": "0cc175b9c0f1b6a831c399e269772661",
                        "sha256": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
                    },
                },
            },
        )
    finally:
        app.dependency_overrides = {}

    assert resp.status_code == 201
    body = resp.json()
    assert body["read_id"] == str(read_obj.id)
    assert sorted(f["file_type"] for f in body["files"]) == ["fastq_r1", "fastq_r2"]
    assert fake_db.qc_read is not None
    assert fake_db.qc_read.read_id == read_obj.id
    assert [f.file_type for f in fake_db.qc_files] == ["fastq_r1", "fastq_r2"]
    assert fake_db.submissions[0].prepared_payload == {
        "files": [
            {
                "filename": "qc/sample_R1.fastq.gz",
                "filetype": "fastq",
                "checksum": "d41d8cd98f00b204e9800998ecf8427e",
                "checksum_method": "MD5",
            },
            {
                "filename": "qc/sample_R2.fastq.gz",
                "filetype": "fastq",
                "checksum": "0cc175b9c0f1b6a831c399e269772661",
                "checksum_method": "MD5",
            },
        ]
    }


def test_report_qc_result_accepts_single_end_fastq():
    client = TestClient(app)
    read_obj = Read(
        id=uuid.uuid4(),
        experiment_id=uuid.uuid4(),
        bpa_resource_id="res-2",
        file_name="input.fastq.gz",
        file_format="fastq",
    )
    fake_db = _SessionQcReport(read_obj=read_obj)
    app.dependency_overrides[qc_reads.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["genome_launcher"], is_superuser=False
    )
    app.dependency_overrides[qc_reads.get_db] = _override_db(fake_db)

    try:
        resp = client.post(
            f"/api/v1/qc-reads/{read_obj.id}/report",
            json={
                "base_count": 200,
                "read_count": 20,
                "qc_bases_removed": 6,
                "qc_reads_removed": 2,
                "mean_gc_content": 39.1,
                "n50_length": None,
                "checksums": {
                    "qc/sample.fastq.gz": {
                        "md5": "900150983cd24fb0d6963f7d28e17f72",
                        "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                    }
                },
            },
        )
    finally:
        app.dependency_overrides = {}

    assert resp.status_code == 201
    assert resp.json()["files"][0]["file_type"] == "fastq"
    assert fake_db.qc_files[0].file_type == "fastq"


def test_report_qc_result_rejects_unlabelled_fastq_pairs():
    client = TestClient(app)
    read_obj = Read(
        id=uuid.uuid4(),
        experiment_id=uuid.uuid4(),
        bpa_resource_id="res-3",
        file_name="input.fastq.gz",
        file_format="fastq",
    )
    fake_db = _SessionQcReport(read_obj=read_obj)
    app.dependency_overrides[qc_reads.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["genome_launcher"], is_superuser=False
    )
    app.dependency_overrides[qc_reads.get_db] = _override_db(fake_db)

    try:
        resp = client.post(
            f"/api/v1/qc-reads/{read_obj.id}/report",
            json={
                "base_count": 200,
                "read_count": 20,
                "qc_bases_removed": 6,
                "qc_reads_removed": 2,
                "mean_gc_content": 39.1,
                "n50_length": None,
                "checksums": {
                    "qc/sample_a.fastq.gz": {
                        "md5": "900150983cd24fb0d6963f7d28e17f72",
                        "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                    },
                    "qc/sample_b.fastq.gz": {
                        "md5": "0cc175b9c0f1b6a831c399e269772661",
                        "sha256": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
                    },
                },
            },
        )
    finally:
        app.dependency_overrides = {}

    assert resp.status_code == 422
    assert "R1/read1" in resp.text
