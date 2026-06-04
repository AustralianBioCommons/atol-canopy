import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import assemblies
from app.main import app
from app.models.assembly import Assembly
from app.models.experiment import Experiment
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
    def __init__(self, assembly_obj=None, experiment_obj=None, read_objs=None):
        self.assembly_obj = assembly_obj
        self.experiment_obj = experiment_obj
        self.read_objs = read_objs or []
        self.qc_read = None
        self.qc_read_assemblies = []
        self.qc_files = []
        self.submissions = []

    def query(self, model):
        if model is Assembly:
            return _QuerySequence(self.assembly_obj)
        if model is Experiment:
            return _QuerySequence(self.experiment_obj)
        if model is Read:
            return _QuerySequence(self.read_objs)
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
    fake_db = _SessionAssemblyQcReport(
        assembly_obj=Assembly(
            id=assembly_id, taxon_id=1, sample_id=uuid.uuid4(), data_types="PACBIO_SMRT"
        ),
        experiment_obj=Experiment(
            id=experiment_id,
            sample_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            bpa_package_id="pkg-1",
        ),
        read_objs=[
            Read(experiment_id=experiment_id, bpa_resource_id="res-1", file_checksum="a" * 32),
            Read(experiment_id=experiment_id, bpa_resource_id="res-2", file_checksum="b" * 32),
        ],
    )
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["genome_launcher"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(fake_db)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        assemblies,
        "_get_allowed_sample_ids_for_assembly",
        lambda db, assembly: {fake_db.experiment_obj.sample_id},
    )
    monkeypatch.setattr(assemblies, "_assembly_manifest_package_ids", lambda assembly: {"pkg-1"})
    try:
        resp = client.post(
            f"/api/v1/assemblies/{assembly_id}/qc-reads/report",
            json={
                "bpa_package_id": "pkg-1",
                "source_read_file_checksums": [
                    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                ],
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
        monkeypatch.undo()
        app.dependency_overrides = {}

    assert resp.status_code == 201
    body = resp.json()
    assert body["experiment_id"] == str(experiment_id)
    assert body["source_read_file_checksums"] == [
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    ]
    assert sorted(f["file_type"] for f in body["files"]) == ["fastq_r1", "fastq_r2"]
    assert fake_db.qc_read is not None
    assert fake_db.qc_read.experiment_id == experiment_id
    assert fake_db.qc_read.source_read_file_checksums == [
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    ]
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
    fake_db = _SessionAssemblyQcReport(
        assembly_obj=Assembly(
            id=assembly_id, taxon_id=1, sample_id=uuid.uuid4(), data_types="PACBIO_SMRT"
        ),
        experiment_obj=Experiment(
            id=experiment_id,
            sample_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            bpa_package_id="pkg-1",
        ),
        read_objs=[
            Read(
                experiment_id=experiment_id,
                bpa_resource_id="res-1",
                file_checksum="900150983cd24fb0d6963f7d28e17f72",
            )
        ],
    )
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["genome_launcher"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(fake_db)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        assemblies,
        "_get_allowed_sample_ids_for_assembly",
        lambda db, assembly: {fake_db.experiment_obj.sample_id},
    )
    monkeypatch.setattr(assemblies, "_assembly_manifest_package_ids", lambda assembly: {"pkg-1"})
    try:
        resp = client.post(
            f"/api/v1/assemblies/{assembly_id}/qc-reads/report",
            json={
                "bpa_package_id": "pkg-1",
                "source_read_file_checksums": ["900150983cd24fb0d6963f7d28e17f72"],
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
        monkeypatch.undo()
        app.dependency_overrides = {}

    assert resp.status_code == 201
    assert resp.json()["files"][0]["file_type"] == "fastq"
    assert fake_db.qc_files[0].file_type == "fastq"


def test_report_qc_result_rejects_unlabelled_fastq_pairs():
    client = TestClient(app)
    assembly_id = uuid.uuid4()
    experiment_id = uuid.uuid4()
    fake_db = _SessionAssemblyQcReport(
        assembly_obj=Assembly(
            id=assembly_id, taxon_id=1, sample_id=uuid.uuid4(), data_types="PACBIO_SMRT"
        ),
        experiment_obj=Experiment(
            id=experiment_id,
            sample_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            bpa_package_id="pkg-1",
        ),
        read_objs=[
            Read(experiment_id=experiment_id, bpa_resource_id="res-1", file_checksum="a" * 32),
            Read(experiment_id=experiment_id, bpa_resource_id="res-2", file_checksum="b" * 32),
        ],
    )
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["genome_launcher"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(fake_db)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        assemblies,
        "_get_allowed_sample_ids_for_assembly",
        lambda db, assembly: {fake_db.experiment_obj.sample_id},
    )
    monkeypatch.setattr(assemblies, "_assembly_manifest_package_ids", lambda assembly: {"pkg-1"})
    try:
        resp = client.post(
            f"/api/v1/assemblies/{assembly_id}/qc-reads/report",
            json={
                "bpa_package_id": "pkg-1",
                "source_read_file_checksums": [
                    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                ],
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
        monkeypatch.undo()
        app.dependency_overrides = {}

    assert resp.status_code == 422
    assert "R1/read1" in resp.text


def test_report_qc_result_rejects_experiment_outside_assembly_lineage():
    client = TestClient(app)
    assembly_id = uuid.uuid4()
    experiment_id = uuid.uuid4()
    fake_db = _SessionAssemblyQcReport(
        assembly_obj=Assembly(
            id=assembly_id, taxon_id=1, sample_id=uuid.uuid4(), data_types="PACBIO_SMRT"
        ),
        experiment_obj=Experiment(
            id=experiment_id,
            sample_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            bpa_package_id="pkg-1",
        ),
        read_objs=[
            Read(
                experiment_id=experiment_id,
                bpa_resource_id="res-1",
                file_checksum="900150983cd24fb0d6963f7d28e17f72",
            )
        ],
    )
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["genome_launcher"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(fake_db)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        assemblies, "_get_allowed_sample_ids_for_assembly", lambda db, assembly: set()
    )
    monkeypatch.setattr(assemblies, "_assembly_manifest_package_ids", lambda assembly: {"pkg-1"})
    try:
        resp = client.post(
            f"/api/v1/assemblies/{assembly_id}/qc-reads/report",
            json={
                "bpa_package_id": "pkg-1",
                "source_read_file_checksums": ["900150983cd24fb0d6963f7d28e17f72"],
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
        monkeypatch.undo()
        app.dependency_overrides = {}

    assert resp.status_code == 422
    assert "specimen lineage" in resp.text


def test_report_qc_result_rejects_experiment_missing_from_manifest():
    client = TestClient(app)
    assembly_id = uuid.uuid4()
    experiment_id = uuid.uuid4()
    fake_db = _SessionAssemblyQcReport(
        assembly_obj=Assembly(
            id=assembly_id, taxon_id=1, sample_id=uuid.uuid4(), data_types="PACBIO_SMRT"
        ),
        experiment_obj=Experiment(
            id=experiment_id,
            sample_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            bpa_package_id="pkg-1",
        ),
        read_objs=[
            Read(
                experiment_id=experiment_id,
                bpa_resource_id="res-1",
                file_checksum="900150983cd24fb0d6963f7d28e17f72",
            )
        ],
    )
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["genome_launcher"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(fake_db)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        assemblies,
        "_get_allowed_sample_ids_for_assembly",
        lambda db, assembly: {fake_db.experiment_obj.sample_id},
    )
    monkeypatch.setattr(assemblies, "_assembly_manifest_package_ids", lambda assembly: {"pkg-2"})
    try:
        resp = client.post(
            f"/api/v1/assemblies/{assembly_id}/qc-reads/report",
            json={
                "bpa_package_id": "pkg-1",
                "source_read_file_checksums": ["900150983cd24fb0d6963f7d28e17f72"],
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
        monkeypatch.undo()
        app.dependency_overrides = {}

    assert resp.status_code == 422
    assert "manifest inputs" in resp.text


def test_report_qc_result_rejects_missing_source_md5_for_experiment():
    client = TestClient(app)
    assembly_id = uuid.uuid4()
    experiment_id = uuid.uuid4()
    fake_db = _SessionAssemblyQcReport(
        assembly_obj=Assembly(
            id=assembly_id, taxon_id=1, sample_id=uuid.uuid4(), data_types="PACBIO_SMRT"
        ),
        experiment_obj=Experiment(
            id=experiment_id,
            sample_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            bpa_package_id="pkg-1",
        ),
        read_objs=[
            Read(
                experiment_id=experiment_id,
                bpa_resource_id="res-1",
                file_checksum="900150983cd24fb0d6963f7d28e17f72",
            )
        ],
    )
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["genome_launcher"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(fake_db)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        assemblies,
        "_get_allowed_sample_ids_for_assembly",
        lambda db, assembly: {fake_db.experiment_obj.sample_id},
    )
    monkeypatch.setattr(assemblies, "_assembly_manifest_package_ids", lambda assembly: {"pkg-1"})
    try:
        resp = client.post(
            f"/api/v1/assemblies/{assembly_id}/qc-reads/report",
            json={
                "bpa_package_id": "pkg-1",
                "source_read_file_checksums": [
                    "900150983cd24fb0d6963f7d28e17f72",
                    "0cc175b9c0f1b6a831c399e269772661",
                ],
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
        monkeypatch.undo()
        app.dependency_overrides = {}

    assert resp.status_code == 422
    assert "Missing MD5 sums" in resp.text


def test_report_qc_result_rejects_unknown_bpa_package_id():
    client = TestClient(app)
    assembly_id = uuid.uuid4()
    fake_db = _SessionAssemblyQcReport(
        assembly_obj=Assembly(
            id=assembly_id, taxon_id=1, sample_id=uuid.uuid4(), data_types="PACBIO_SMRT"
        ),
        experiment_obj=None,
    )
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["genome_launcher"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(fake_db)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        assemblies, "_get_allowed_sample_ids_for_assembly", lambda db, assembly: set()
    )
    monkeypatch.setattr(assemblies, "_assembly_manifest_package_ids", lambda assembly: set())
    try:
        resp = client.post(
            f"/api/v1/assemblies/{assembly_id}/qc-reads/report",
            json={
                "bpa_package_id": "pkg-1",
                "source_read_file_checksums": ["900150983cd24fb0d6963f7d28e17f72"],
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
        monkeypatch.undo()
        app.dependency_overrides = {}

    assert resp.status_code == 422
    assert "Experiment not found" in resp.text
