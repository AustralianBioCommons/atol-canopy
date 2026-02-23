import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import genome_notes
from app.main import app


class _FakeSession:
    def __init__(self, note=None):
        self._note = note
        self.added = []
        self.committed = False
        self.deleted = []

    def query(self, *_):
        return self

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self._note

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = obj.created_at
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, _obj):
        pass

    def delete(self, obj):
        self.deleted.append(obj)


def _override_db(fake):
    def _gen():
        yield fake

    return _gen


def _override_user():
    return SimpleNamespace(is_superuser=False, roles=["curator"], is_active=True)


def _override_admin_user():
    return SimpleNamespace(is_superuser=False, roles=["admin"], is_active=True)


class TestGetGenomeNote:
    """Tests for GET /genome-notes/{id}"""

    def test_genome_note_not_found(self):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        resp = client.get(f"/api/v1/genome-notes/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_genome_note_found(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user

        note_id = uuid.uuid4()
        assembly_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        fake_note = SimpleNamespace(
            id=note_id,
            organism_key="test_organism",
            assembly_id=assembly_id,
            version=1,
            title="Test Note",
            note_url="https://example.com/note",
            is_published=False,
            published_at=None,
            created_at=now,
            updated_at=now,
        )
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession(fake_note))

        resp = client.get(f"/api/v1/genome-notes/{note_id}")
        assert resp.status_code == 200
        assert resp.json()["version"] == 1
        assert resp.json()["organism_key"] == "test_organism"


class TestListGenomeNotes:
    """Tests for GET /genome-notes/"""

    def test_list_genome_notes_empty(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        fake_service = SimpleNamespace(get_multi_with_filters=lambda db, **_: [])
        monkeypatch.setattr(genome_notes, "genome_note_service", fake_service)

        resp = client.get("/api/v1/genome-notes/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_genome_notes_with_data(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        now = datetime.now(timezone.utc)
        fake_notes = [
            {
                "id": str(uuid.uuid4()),
                "organism_key": "organism_1",
                "assembly_id": str(uuid.uuid4()),
                "version": 2,
                "title": "Note 1",
                "note_url": "https://example.com/note1",
                "is_published": True,
                "published_at": now.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
            {
                "id": str(uuid.uuid4()),
                "organism_key": "organism_2",
                "assembly_id": str(uuid.uuid4()),
                "version": 1,
                "title": "Note 2",
                "note_url": "https://example.com/note2",
                "is_published": False,
                "published_at": None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        ]

        fake_service = SimpleNamespace(get_multi_with_filters=lambda db, **_: fake_notes)
        monkeypatch.setattr(genome_notes, "genome_note_service", fake_service)

        resp = client.get("/api/v1/genome-notes/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestCreateGenomeNote:
    """Tests for POST /genome-notes/"""

    def test_create_genome_note_success(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        note_id = uuid.uuid4()
        assembly_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        monkeypatch.setattr(
            genome_notes,
            "genome_note_service",
            SimpleNamespace(get_next_version=lambda db, organism_key: 1),
        )

        payload = {
            "organism_key": "test_organism",
            "assembly_id": str(assembly_id),
            "title": "New Genome Note",
            "note_url": "https://example.com/new-note",
        }

        resp = client.post("/api/v1/genome-notes/", json=payload)
        assert resp.status_code == 200
        assert resp.json()["version"] == 1
        assert resp.json()["title"] == "New Genome Note"
        assert resp.json()["is_published"] is False

    def test_create_genome_note_auto_version(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        assembly_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        monkeypatch.setattr(
            genome_notes,
            "genome_note_service",
            SimpleNamespace(get_next_version=lambda db, organism_key: 3),
        )

        payload = {
            "organism_key": "existing_organism",
            "assembly_id": str(assembly_id),
            "title": "Version 3",
            "note_url": "https://example.com/v3",
        }

        resp = client.post("/api/v1/genome-notes/", json=payload)
        assert resp.status_code == 200
        assert resp.json()["version"] == 3


class TestUpdateGenomeNote:
    """Tests for PUT /genome-notes/{id}"""

    def test_update_genome_note_success(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        note_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        fake_note = SimpleNamespace(
            id=note_id,
            organism_key="test_organism",
            assembly_id=uuid.uuid4(),
            version=1,
            title="Original Title",
            note_url="https://example.com/original",
            is_published=False,
            published_at=None,
            created_at=now,
            updated_at=now,
        )
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession(fake_note))

        payload = {"title": "Updated Title"}

        resp = client.put(f"/api/v1/genome-notes/{note_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_update_genome_note_not_found(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        note_id = uuid.uuid4()

        payload = {"title": "Updated Title"}

        resp = client.put(f"/api/v1/genome-notes/{note_id}", json=payload)
        assert resp.status_code == 404


class TestDeleteGenomeNote:
    """Tests for DELETE /genome-notes/{id}"""

    def test_delete_genome_note_success(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_admin_user
        note_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        fake_note = SimpleNamespace(
            id=note_id,
            organism_key="test_organism",
            assembly_id=uuid.uuid4(),
            version=1,
            title="Original Title",
            note_url="https://example.com/original",
            is_published=False,
            published_at=None,
            created_at=now,
            updated_at=now,
        )
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession(fake_note))

        resp = client.delete(f"/api/v1/genome-notes/{note_id}")
        assert resp.status_code == 200

    def test_delete_genome_note_not_found(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_admin_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        note_id = uuid.uuid4()

        resp = client.delete(f"/api/v1/genome-notes/{note_id}")
        assert resp.status_code == 404


class TestPublishGenomeNote:
    """Tests for POST /genome-notes/{id}/publish"""

    def test_publish_genome_note_success(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        note_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        def fake_publish(db, note_id):
            return {
                "id": str(note_id),
                "organism_key": "test_organism",
                "assembly_id": str(uuid.uuid4()),
                "version": 1,
                "title": "Published Note",
                "note_url": "https://example.com/note",
                "is_published": True,
                "published_at": now.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }

        fake_service = SimpleNamespace(publish_genome_note=fake_publish)
        monkeypatch.setattr(genome_notes, "genome_note_service", fake_service)

        resp = client.post(f"/api/v1/genome-notes/{note_id}/publish")
        assert resp.status_code == 200
        assert resp.json()["is_published"] is True
        assert resp.json()["published_at"] is not None

    def test_publish_genome_note_conflict(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        note_id = uuid.uuid4()

        def fake_publish(db, note_id):
            raise ValueError(
                "Organism 'test_organism' already has a published genome note (version 2). "
                "Please unpublish it first."
            )

        fake_service = SimpleNamespace(publish_genome_note=fake_publish)
        monkeypatch.setattr(genome_notes, "genome_note_service", fake_service)

        resp = client.post(f"/api/v1/genome-notes/{note_id}/publish")
        assert resp.status_code == 409
        assert "already has a published genome note" in resp.json()["error"]["message"]

    def test_publish_genome_note_not_found(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        note_id = uuid.uuid4()

        def fake_publish(db, note_id):
            raise ValueError("Genome note not found")

        fake_service = SimpleNamespace(publish_genome_note=fake_publish)
        monkeypatch.setattr(genome_notes, "genome_note_service", fake_service)

        resp = client.post(f"/api/v1/genome-notes/{note_id}/publish")
        assert resp.status_code == 404


class TestUnpublishGenomeNote:
    """Tests for POST /genome-notes/{id}/unpublish"""

    def test_unpublish_genome_note_success(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        note_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        def fake_unpublish(db, note_id):
            return {
                "id": str(note_id),
                "organism_key": "test_organism",
                "assembly_id": str(uuid.uuid4()),
                "version": 1,
                "title": "Unpublished Note",
                "note_url": "https://example.com/note",
                "is_published": False,
                "published_at": None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }

        fake_service = SimpleNamespace(unpublish_genome_note=fake_unpublish)
        monkeypatch.setattr(genome_notes, "genome_note_service", fake_service)

        resp = client.post(f"/api/v1/genome-notes/{note_id}/unpublish")
        assert resp.status_code == 200
        assert resp.json()["is_published"] is False
        assert resp.json()["published_at"] is None

    def test_unpublish_genome_note_not_found(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        note_id = uuid.uuid4()

        def fake_unpublish(db, note_id):
            raise ValueError("Genome note not found")

        fake_service = SimpleNamespace(unpublish_genome_note=fake_unpublish)
        monkeypatch.setattr(genome_notes, "genome_note_service", fake_service)

        resp = client.post(f"/api/v1/genome-notes/{note_id}/unpublish")
        assert resp.status_code == 404


class TestGetPublishedByOrganism:
    """Tests for GET /genome-notes/organism/{organism_key}/published"""

    def test_get_published_by_organism_found(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        now = datetime.now(timezone.utc)

        fake_note = {
            "id": str(uuid.uuid4()),
            "organism_key": "test_organism",
            "assembly_id": str(uuid.uuid4()),
            "version": 2,
            "title": "Published Note",
            "note_url": "https://example.com/note",
            "is_published": True,
            "published_at": now.isoformat(),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        fake_service = SimpleNamespace(get_published_by_organism=lambda db, organism_key: fake_note)
        monkeypatch.setattr(genome_notes, "genome_note_service", fake_service)

        resp = client.get("/api/v1/genome-notes/organism/test_organism/published")
        assert resp.status_code == 200
        assert resp.json()["is_published"] is True
        assert resp.json()["version"] == 2

    def test_get_published_by_organism_not_found(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        fake_service = SimpleNamespace(get_published_by_organism=lambda db, organism_key: None)
        monkeypatch.setattr(genome_notes, "genome_note_service", fake_service)

        resp = client.get("/api/v1/genome-notes/organism/test_organism/published")
        assert resp.status_code == 404


class TestGetVersionsByOrganism:
    """Tests for GET /genome-notes/organism/{organism_key}/versions"""

    def test_get_versions_by_organism(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        now = datetime.now(timezone.utc)

        fake_notes = [
            {
                "id": str(uuid.uuid4()),
                "organism_key": "test_organism",
                "assembly_id": str(uuid.uuid4()),
                "version": 3,
                "title": "Version 3",
                "note_url": "https://example.com/v3",
                "is_published": True,
                "published_at": now.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
            {
                "id": str(uuid.uuid4()),
                "organism_key": "test_organism",
                "assembly_id": str(uuid.uuid4()),
                "version": 2,
                "title": "Version 2",
                "note_url": "https://example.com/v2",
                "is_published": False,
                "published_at": None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
            {
                "id": str(uuid.uuid4()),
                "organism_key": "test_organism",
                "assembly_id": str(uuid.uuid4()),
                "version": 1,
                "title": "Version 1",
                "note_url": "https://example.com/v1",
                "is_published": False,
                "published_at": None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        ]

        fake_service = SimpleNamespace(get_versions_by_organism=lambda db, organism_key: fake_notes)
        monkeypatch.setattr(genome_notes, "genome_note_service", fake_service)

        resp = client.get("/api/v1/genome-notes/organism/test_organism/versions")
        assert resp.status_code == 200
        assert len(resp.json()) == 3
        assert resp.json()[0]["version"] == 3
        assert resp.json()[1]["version"] == 2
        assert resp.json()[2]["version"] == 1

    def test_get_versions_by_organism_empty(self, monkeypatch):
        client = TestClient(app)
        app.dependency_overrides[genome_notes.get_current_active_user] = _override_user
        app.dependency_overrides[genome_notes.get_db] = _override_db(_FakeSession())

        fake_service = SimpleNamespace(get_versions_by_organism=lambda db, organism_key: [])
        monkeypatch.setattr(genome_notes, "genome_note_service", fake_service)

        resp = client.get("/api/v1/genome-notes/organism/test_organism/versions")
        assert resp.status_code == 200
        assert resp.json() == []
