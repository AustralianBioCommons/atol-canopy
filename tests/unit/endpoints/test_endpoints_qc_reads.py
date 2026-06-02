import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import assemblies
from app.main import app
from app.models.assembly import Assembly, AssemblyRead
from app.models.qc_read import QcRead, QcReadAssembly, QcReadFile, QcReadSubmission
from app.models.read import Read


def _override_db(fake):
    def _gen():
        yield fake

    return _gen


class _QuerySequence:
    def __init__(self, value):
        self.value = value

    def filter(self, *_a, **_k):
        return self

    def join(self, *_a, **_k):
        return self

    def first(self):
        return self.value if not isinstance(self.value, list) else None

    def all(self):
        return self.value if isinstance(self.value, list) else []


class _SessionAssemblyQcReport:
    def __init__(self, assembly_obj=None, read_rows=None, assembly_read_rows=None):
        self.assembly_obj = assembly_obj
        self.read_rows = read_rows or []
        self.assembly_read_rows = assembly_read_rows or []
        self.qc_read = None
        self.qc_read_assemblies = []
        self.qc_files = []
        self.submissions = []

    def query(self, model):
        if model is Assembly:
            return _QuerySequence(self.assembly_obj)
        if model is Read:
            return _QuerySequence(self.read_rows)
        if model is AssemblyRead:
            return _QuerySequence(self.assembly_read_rows)
        return _QuerySequence(None)

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
        elif isinstance(obj, QcReadAssembly):
            self.qc_read_assemblies.append(obj)
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
    assembly_id = uuid.uuid4()
    experiment_id = uuid.uuid4()
    read_1 = Read(id=uuid.uuid4(), experiment_id=experiment_id, bpa_resource_id="res-1")
    read_2 = Read(id=uuid.uuid4(), experiment_id=experiment_id, bpa_resource_id="res-2")
    fake_db = _SessionAssemblyQcReport(
        assembly_obj=Assembly(id=assembly_id, taxon_id=1, sample_id=uuid.uuid4(), data_types="PACBIO_SMRT"),
        read_rows=[read_1, read_2],
        assembly_read_rows=[
            SimpleNamespace(assembly_id=assembly_id, read_id=read_1.id),
            SimpleNamespace(assembly_id=assembly_id, read_id=read_2.id),
        ],
    )
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["genome_launcher"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(fake_db)

    try:
        resp = client.post(
            f"/api/v1/assemblies/{assembly_id}/qc-reads/report",
            json={
                "source_bpa_resource_ids": ["res-1", "res-2"],
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
    assert body["experiment_id"] == str(experiment_id)
    assert body["source_bpa_resource_ids"] == ["res-1", "res-2"]
    assert sorted(f["file_type"] for f in body["files"]) == ["fastq_r1", "fastq_r2"]
    assert fake_db.qc_read is not None
    assert fake_db.qc_read.experiment_id == experiment_id
    assert fake_db.qc_read.source_bpa_resource_ids == ["res-1", "res-2"]
    assert [f.file_type for f in fake_db.qc_files] == ["fastq_r1", "fastq_r2"]
    assert fake_db.qc_read_assemblies[0].assembly_id == assembly_id
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
    assembly_id = uuid.uuid4()
    experiment_id = uuid.uuid4()
    read_1 = Read(id=uuid.uuid4(), experiment_id=experiment_id, bpa_resource_id="res-1")
    fake_db = _SessionAssemblyQcReport(
        assembly_obj=Assembly(id=assembly_id, taxon_id=1, sample_id=uuid.uuid4(), data_types="PACBIO_SMRT"),
        read_rows=[read_1],
        assembly_read_rows=[SimpleNamespace(assembly_id=assembly_id, read_id=read_1.id)],
    )
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["genome_launcher"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(fake_db)

    try:
        resp = client.post(
            f"/api/v1/assemblies/{assembly_id}/qc-reads/report",
            json={
                "source_bpa_resource_ids": ["res-1"],
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
    assembly_id = uuid.uuid4()
    fake_db = _SessionAssemblyQcReport(
        assembly_obj=Assembly(id=assembly_id, taxon_id=1, sample_id=uuid.uuid4(), data_types="PACBIO_SMRT")
    )
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["genome_launcher"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(fake_db)

    try:
        resp = client.post(
            f"/api/v1/assemblies/{assembly_id}/qc-reads/report",
            json={
                "source_bpa_resource_ids": ["res-1", "res-2"],
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
