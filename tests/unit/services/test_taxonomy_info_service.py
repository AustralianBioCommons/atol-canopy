import pytest

from app.models.organism import Organism
from app.models.taxonomy_info import TaxonomyInfo
from app.schemas.bulk_import import BulkTaxonomyInfoImport
from app.schemas.taxonomy_info import TaxonomyInfoCreate
from app.services import taxonomy_info_service as ti_service_module


class _Query:
    def __init__(self, session, model):
        self.session = session
        self.model = model
        self._taxon_id = None

    def filter(self, *criteria, **_kwargs):
        for criterion in criteria:
            right = getattr(criterion, "right", None)
            value = getattr(right, "value", None)
            if value is not None:
                self._taxon_id = value
        return self

    def first(self):
        store = self.session.data.get(self.model, {})
        if self._taxon_id is None:
            return next(iter(store.values()), None)
        return store.get(self._taxon_id)


class _Session:
    def __init__(self, data=None):
        self.data = data or {}
        self.commit_count = 0
        self.flush_count = 0
        self.refresh_count = 0

    def query(self, model):
        return _Query(self, model)

    def add(self, obj):
        if isinstance(obj, (Organism, TaxonomyInfo)):
            self.data.setdefault(type(obj), {})
            self.data[type(obj)][obj.taxon_id] = obj

    def delete(self, obj):
        store = self.data.get(type(obj), {})
        store.pop(obj.taxon_id, None)

    def commit(self):
        self.commit_count += 1

    def flush(self):
        self.flush_count += 1

    def refresh(self, _obj):
        self.refresh_count += 1

    def rollback(self):
        pass


def test_populate_from_ncbi_lookup_creates_taxonomy_info(monkeypatch):
    organism = Organism(taxon_id=5077, bpa_scientific_name="Penicillium")
    db = _Session({Organism: {5077: organism}, TaxonomyInfo: {}})
    calls = []

    monkeypatch.setattr(
        ti_service_module,
        "fetch_taxonomy_for_taxon_ids",
        lambda taxa, batch_size=20: (
            calls.append((taxa, batch_size))
            or {
                5077: {
                    "taxon_id": 5077,
                    "ncbi_taxon_id": 5077,
                    "ncbi_rank": "species",
                    "ncbi_scientific_name": "Penicillium test",
                    "ncbi_order": "Eurotiales",
                    "mitohifi_reference_species": "Penicillium chrysogenum",
                }
            },
            [],
        ),
    )

    ti = ti_service_module.taxonomy_info_service.populate_from_ncbi_lookup(
        db,
        taxon_id=5077,
        scientific_name="Penicillium",
        commit=False,
    )

    assert ti is not None
    assert calls == [({5077: "Penicillium"}, 20)]
    assert ti.taxon_id == 5077
    assert ti.ncbi_taxon_id == 5077
    assert ti.ncbi_rank == "species"
    assert ti.ncbi_order == "Eurotiales"
    assert ti.mitohifi_reference_species == "Penicillium chrysogenum"
    assert ti.ncbi_last_synced_at is not None
    assert organism.scientific_name == "Penicillium test"
    assert db.data[TaxonomyInfo][5077] is ti
    assert db.flush_count == 1
    assert db.commit_count == 0


def test_create_taxonomy_info_fetches_ncbi_and_applies_payload(monkeypatch):
    organism = Organism(taxon_id=5303, bpa_scientific_name="Agaricus")
    db = _Session({Organism: {5303: organism}, TaxonomyInfo: {}})
    calls = []

    monkeypatch.setattr(
        ti_service_module,
        "fetch_taxonomy_for_taxon_ids",
        lambda taxa, batch_size=20: (
            calls.append((taxa, batch_size))
            or {
                5303: {
                    "taxon_id": 5303,
                    "ncbi_taxon_id": 5303,
                    "ncbi_rank": "species",
                    "ncbi_scientific_name": "Agaricus test",
                }
            },
            [],
        ),
    )

    ti = ti_service_module.taxonomy_info_service.create(
        db,
        ti_in=TaxonomyInfoCreate(
            taxon_id=5303,
            genetic_code_id=11,
            augustus_dataset_name="agaricus_aug",
        ),
    )

    assert ti.taxon_id == 5303
    assert calls == [({5303: "Agaricus"}, 20)]
    assert ti.ncbi_taxon_id == 5303
    assert ti.ncbi_rank == "species"
    assert ti.ncbi_last_synced_at is not None
    assert ti.genetic_code_id == 11
    assert ti.augustus_dataset_name == "agaricus_aug"
    assert organism.scientific_name == "Agaricus test"
    assert db.commit_count == 1
    assert db.refresh_count == 1


def test_taxonomy_info_create_rejects_ncbi_fields():
    with pytest.raises(Exception):
        TaxonomyInfoCreate(
            taxon_id=5304,
            ncbi_rank="genus",
            genetic_code_id=3,
        )


def test_bulk_import_batches_ncbi_lookup_and_creates_taxonomy_info(monkeypatch):
    organisms = {
        9612: Organism(taxon_id=9612, bpa_scientific_name="Canis lupus"),
        9685: Organism(taxon_id=9685, bpa_scientific_name="Felis catus"),
    }
    db = _Session({Organism: organisms, TaxonomyInfo: {}})
    calls = []

    monkeypatch.setattr(
        ti_service_module,
        "fetch_taxonomy_for_taxon_ids",
        lambda taxa, batch_size=20: (
            calls.append((taxa, batch_size))
            or {
                9612: {
                    "taxon_id": 9612,
                    "ncbi_taxon_id": 9612,
                    "ncbi_rank": "species",
                    "ncbi_scientific_name": "Canis lupus familiaris",
                    "mitohifi_reference_species": "Canis lupus familiaris",
                },
                9685: {
                    "taxon_id": 9685,
                    "ncbi_taxon_id": 9685,
                    "ncbi_rank": "species",
                    "ncbi_scientific_name": "Felis silvestris catus",
                    "mitohifi_reference_species": "Felis silvestris catus",
                },
            },
            [],
        ),
    )

    result = ti_service_module.taxonomy_info_service.bulk_import(
        db,
        data=BulkTaxonomyInfoImport.model_validate(
            {
                "9612": {"genetic_code_id": 2},
                "9685": {"genetic_code_id": 1},
            }
        ).root,
    )

    assert calls == [({9612: "Canis lupus", 9685: "Felis catus"}, 20)]
    assert result.created_count == 2
    assert result.skipped_count == 0
    saved_dog = db.data[TaxonomyInfo][9612]
    saved_cat = db.data[TaxonomyInfo][9685]
    assert saved_dog.ncbi_taxon_id == 9612
    assert saved_dog.ncbi_rank == "species"
    assert saved_dog.mitohifi_reference_species == "Canis lupus familiaris"
    assert saved_dog.ncbi_last_synced_at is not None
    assert saved_dog.genetic_code_id == 2
    assert saved_cat.ncbi_taxon_id == 9685
    assert saved_cat.ncbi_rank == "species"
    assert saved_cat.mitohifi_reference_species == "Felis silvestris catus"
    assert saved_cat.ncbi_last_synced_at is not None
    assert saved_cat.genetic_code_id == 1
    assert organisms[9612].scientific_name == "Canis lupus familiaris"
    assert organisms[9685].scientific_name == "Felis silvestris catus"


def test_delete_taxonomy_info_falls_back_to_bpa_scientific_name():
    organism = Organism(
        taxon_id=5303,
        scientific_name="Agaricus test",
        bpa_scientific_name="Agaricus",
    )
    ti = TaxonomyInfo(taxon_id=5303, ncbi_scientific_name="Agaricus test")
    db = _Session({Organism: {5303: organism}, TaxonomyInfo: {5303: ti}})

    deleted = ti_service_module.taxonomy_info_service.delete(db, taxon_id=5303)

    assert deleted is ti
    assert organism.scientific_name == "Agaricus"
    assert db.commit_count == 1


def test_bulk_import_schema_rejects_ncbi_fields():
    with pytest.raises(Exception):
        BulkTaxonomyInfoImport.model_validate(
            {"9612": {"ncbi_rank": "species", "genetic_code_id": 2}}
        )
