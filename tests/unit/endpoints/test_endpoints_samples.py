import uuid
from types import SimpleNamespace
from urllib.parse import quote

from fastapi.testclient import TestClient

from app.api.v1.endpoints import samples
from app.main import app


class _FakeSession:
    def query(self, *_):
        return self

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return None


def _override_db(fake):
    def _gen():
        yield fake

    return _gen


def test_sample_not_found():
    client = TestClient(app)
    app.dependency_overrides[samples.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[samples.get_db] = _override_db(_FakeSession())

    resp = client.get(f"/api/v1/samples/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_get_samples_experiments_and_reads_for_specimen():
    client = TestClient(app)

    taxon_id = 172942
    specimen_id = "SPEC-001"
    specimen_sample_id = uuid.uuid4()
    derived_sample_id = uuid.uuid4()
    experiment_1_id = uuid.uuid4()
    experiment_2_id = uuid.uuid4()
    read_1_id = uuid.uuid4()
    read_2_id = uuid.uuid4()

    organism = SimpleNamespace(taxon_id=taxon_id, scientific_name="Test species")
    specimen_sample = SimpleNamespace(
        id=specimen_sample_id,
        taxon_id=taxon_id,
        specimen_id=specimen_id,
        kind="specimen",
        bpa_sample_id=None,
        specimen_id_description=None,
        identified_by=None,
        specimen_custodian=None,
        sample_custodian=None,
        lifestage="adult",
        sex="female",
        organism_part="whole organism",
        region_and_locality="region",
        state_or_region=None,
        country_or_sea="Australia",
        indigenous_location=None,
        latitude=None,
        longitude=None,
        elevation=None,
        depth=None,
        habitat="forest",
        collection_method=None,
        collection_date=None,
        collected_by="collector",
        collecting_institution="institution",
        collection_permit=None,
        data_context=None,
        bioplatforms_project_id=None,
        title=None,
        sample_same_as=None,
        sample_derived_from=None,
        specimen_voucher=None,
        tolid=None,
        preservation_method=None,
        preservation_temperature=None,
        project_name=None,
        biosample_accession=None,
        derived_from_sample_id=None,
        extensions=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    derived_sample = SimpleNamespace(
        id=derived_sample_id,
        taxon_id=taxon_id,
        specimen_id=specimen_id,
        kind="derived",
        bpa_sample_id="BPA-001",
        specimen_id_description=None,
        identified_by=None,
        specimen_custodian=None,
        sample_custodian=None,
        lifestage="adult",
        sex="female",
        organism_part="tissue",
        region_and_locality="region",
        state_or_region=None,
        country_or_sea="Australia",
        indigenous_location=None,
        latitude=None,
        longitude=None,
        elevation=None,
        depth=None,
        habitat="forest",
        collection_method=None,
        collection_date=None,
        collected_by="collector",
        collecting_institution="institution",
        collection_permit=None,
        data_context=None,
        bioplatforms_project_id=None,
        title=None,
        sample_same_as=None,
        sample_derived_from=None,
        specimen_voucher=None,
        tolid=None,
        preservation_method=None,
        preservation_temperature=None,
        project_name=None,
        biosample_accession=None,
        derived_from_sample_id=specimen_sample_id,
        extensions=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    experiment_1 = SimpleNamespace(
        id=experiment_1_id,
        sample_id=specimen_sample_id,
        project_id=uuid.uuid4(),
        bpa_package_id="PKG-001",
        bioplatforms_base_url="https://example.com/pkg-001",
        design_description="long-read library",
        bpa_library_id="LIB-001",
        library_strategy="WGS",
        library_source="GENOMIC",
        insert_size=None,
        library_construction_protocol="protocol",
        library_selection="size selected",
        library_layout="SINGLE",
        instrument_model="Sequel II",
        platform="PACBIO_SMRT",
        material_extracted_by="lab-a",
        library_prepared_by="lab-b",
        sequencing_kit="kit-a",
        flowcell_type="flowcell-a",
        base_caller_model=None,
        data_owner="owner-a",
        project_collaborators="collab-a",
        extraction_method="method-a",
        nucleic_acid_treatment=None,
        extraction_protocol_doi=None,
        nucleic_acid_conc="10",
        nucleic_acid_volume="5",
        gal=None,
        raw_data_release_date="2026-01-10",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    experiment_2 = SimpleNamespace(
        id=experiment_2_id,
        sample_id=derived_sample_id,
        project_id=uuid.uuid4(),
        bpa_package_id="PKG-002",
        bioplatforms_base_url="https://example.com/pkg-002",
        design_description="derived library",
        bpa_library_id="LIB-002",
        library_strategy="Hi-C",
        library_source="GENOMIC",
        insert_size=None,
        library_construction_protocol="protocol-2",
        library_selection="selection-2",
        library_layout="PAIRED",
        instrument_model="NovaSeq",
        platform="ILLUMINA",
        material_extracted_by="lab-c",
        library_prepared_by="lab-d",
        sequencing_kit="kit-b",
        flowcell_type="flowcell-b",
        base_caller_model=None,
        data_owner="owner-b",
        project_collaborators="collab-b",
        extraction_method="method-b",
        nucleic_acid_treatment=None,
        extraction_protocol_doi=None,
        nucleic_acid_conc="20",
        nucleic_acid_volume="10",
        gal=None,
        raw_data_release_date="2026-02-10",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    read_1 = SimpleNamespace(
        id=read_1_id,
        experiment_id=experiment_1_id,
        bpa_resource_id="RES-001",
        bpa_dataset_id="DATASET-001",
        file_name="reads1.ccs.bam",
        file_checksum="md5-1",
        file_format="bam",
        optional_file=False,
        bioplatforms_url="https://example.com/reads1.ccs.bam",
        read_number=None,
        lane_number=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    read_2 = SimpleNamespace(
        id=read_2_id,
        experiment_id=experiment_2_id,
        bpa_resource_id="RES-002",
        bpa_dataset_id="DATASET-002",
        file_name="reads2_R1.fastq.gz",
        file_checksum="md5-2",
        file_format="fastq.gz",
        optional_file=True,
        bioplatforms_url="https://example.com/reads2_R1.fastq.gz",
        read_number="1",
        lane_number="L001",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )

    class _Q:
        def __init__(self, value):
            self.value = value

        def filter(self, *_a, **_k):
            return self

        def first(self):
            return self.value if not isinstance(self.value, list) else None

        def all(self):
            return self.value if isinstance(self.value, list) else []

    class _DB:
        def __init__(self):
            self.calls = 0

        def query(self, _model):
            self.calls += 1
            if self.calls == 1:
                return _Q(organism)
            if self.calls == 2:
                return _Q(specimen_sample)
            if self.calls == 3:
                return _Q([specimen_sample, derived_sample])
            if self.calls == 4:
                return _Q([experiment_1])
            if self.calls == 5:
                return _Q([read_1])
            if self.calls == 6:
                return _Q([experiment_2])
            if self.calls == 7:
                return _Q([read_2])
            return _Q([])

    app.dependency_overrides[samples.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[samples.get_db] = _override_db(_DB())

    resp = client.get(f"/api/v1/samples/by-specimen/{taxon_id}/{specimen_id}/related")

    assert resp.status_code == 200
    body = resp.json()
    assert body["taxon_id"] == taxon_id
    assert body["specimen_id"] == specimen_id
    assert len(body["samples"]) == 2
    assert body["samples"][0]["sample"]["id"] == str(specimen_sample_id)
    assert body["samples"][0]["experiments"][0]["experiment"]["id"] == str(experiment_1_id)
    assert body["samples"][0]["experiments"][0]["experiment"]["platform"] == "PACBIO_SMRT"
    assert body["samples"][0]["experiments"][0]["reads"][0]["id"] == str(read_1_id)
    assert body["samples"][0]["experiments"][0]["reads"][0]["file_name"] == "reads1.ccs.bam"
    assert body["samples"][1]["sample"]["id"] == str(derived_sample_id)
    assert body["samples"][1]["experiments"][0]["experiment"]["id"] == str(experiment_2_id)
    assert body["samples"][1]["experiments"][0]["experiment"]["library_layout"] == "PAIRED"
    assert body["samples"][1]["experiments"][0]["reads"][0]["id"] == str(read_2_id)
    assert body["samples"][1]["experiments"][0]["reads"][0]["lane_number"] == "L001"


def test_get_samples_experiments_and_reads_for_specimen_not_found():
    client = TestClient(app)

    taxon_id = 172942
    specimen_id = "SPEC-404"
    organism = SimpleNamespace(taxon_id=taxon_id, scientific_name="Test species")

    class _Q:
        def __init__(self, value):
            self.value = value

        def filter(self, *_a, **_k):
            return self

        def first(self):
            return self.value

    class _DB:
        def __init__(self):
            self.calls = 0

        def query(self, _model):
            self.calls += 1
            if self.calls == 1:
                return _Q(organism)
            return _Q(None)

    app.dependency_overrides[samples.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[samples.get_db] = _override_db(_DB())

    resp = client.get(f"/api/v1/samples/by-specimen/{taxon_id}/{specimen_id}/related")
    assert resp.status_code == 404


def test_get_specimen_by_taxid_and_specimen_id_accepts_encoded_path_value():
    client = TestClient(app)

    taxon_id = 172942
    specimen_id = "SPEC / 001"
    encoded_specimen_id = quote(specimen_id, safe="")
    specimen_sample_id = uuid.uuid4()

    organism = SimpleNamespace(taxon_id=taxon_id, scientific_name="Test species")
    specimen_sample = SimpleNamespace(
        id=specimen_sample_id,
        taxon_id=taxon_id,
        specimen_id=specimen_id,
        kind="specimen",
        bpa_sample_id=None,
        specimen_id_description=None,
        identified_by=None,
        specimen_custodian=None,
        sample_custodian=None,
        lifestage="adult",
        sex="female",
        organism_part="whole organism",
        region_and_locality="region",
        state_or_region=None,
        country_or_sea="Australia",
        indigenous_location=None,
        latitude=None,
        longitude=None,
        elevation=None,
        depth=None,
        habitat="forest",
        collection_method=None,
        collection_date=None,
        collected_by="collector",
        collecting_institution="institution",
        collection_permit=None,
        data_context=None,
        bioplatforms_project_id=None,
        title=None,
        sample_same_as=None,
        sample_derived_from=None,
        specimen_voucher=None,
        tolid=None,
        preservation_method=None,
        preservation_temperature=None,
        project_name=None,
        biosample_accession=None,
        derived_from_sample_id=None,
        extensions=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )

    class _Q:
        def __init__(self, value):
            self.value = value

        def filter(self, *_a, **_k):
            return self

        def first(self):
            return self.value

    class _DB:
        def __init__(self):
            self.calls = 0

        def query(self, _model):
            self.calls += 1
            if self.calls == 1:
                return _Q(organism)
            return _Q(specimen_sample)

    app.dependency_overrides[samples.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[samples.get_db] = _override_db(_DB())

    resp = client.get(f"/api/v1/samples/by-specimen/{taxon_id}/{encoded_specimen_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["specimen_id"] == specimen_id


def test_get_samples_experiments_and_reads_for_specimen_accepts_encoded_path_value():
    client = TestClient(app)

    taxon_id = 172942
    specimen_id = "SPEC / 001"
    encoded_specimen_id = quote(specimen_id, safe="")
    specimen_sample_id = uuid.uuid4()

    organism = SimpleNamespace(taxon_id=taxon_id, scientific_name="Test species")
    specimen_sample = SimpleNamespace(
        id=specimen_sample_id,
        taxon_id=taxon_id,
        specimen_id=specimen_id,
        kind="specimen",
        bpa_sample_id=None,
        specimen_id_description=None,
        identified_by=None,
        specimen_custodian=None,
        sample_custodian=None,
        lifestage="adult",
        sex="female",
        organism_part="whole organism",
        region_and_locality="region",
        state_or_region=None,
        country_or_sea="Australia",
        indigenous_location=None,
        latitude=None,
        longitude=None,
        elevation=None,
        depth=None,
        habitat="forest",
        collection_method=None,
        collection_date=None,
        collected_by="collector",
        collecting_institution="institution",
        collection_permit=None,
        data_context=None,
        bioplatforms_project_id=None,
        title=None,
        sample_same_as=None,
        sample_derived_from=None,
        specimen_voucher=None,
        tolid=None,
        preservation_method=None,
        preservation_temperature=None,
        project_name=None,
        biosample_accession=None,
        derived_from_sample_id=None,
        extensions=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )

    class _Q:
        def __init__(self, value):
            self.value = value

        def filter(self, *_a, **_k):
            return self

        def first(self):
            return self.value if not isinstance(self.value, list) else None

        def all(self):
            return self.value if isinstance(self.value, list) else []

    class _DB:
        def __init__(self):
            self.calls = 0

        def query(self, _model):
            self.calls += 1
            if self.calls == 1:
                return _Q(organism)
            if self.calls == 2:
                return _Q(specimen_sample)
            if self.calls == 3:
                return _Q([specimen_sample])
            if self.calls == 4:
                return _Q([])
            return _Q([])

    app.dependency_overrides[samples.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[samples.get_db] = _override_db(_DB())

    resp = client.get(f"/api/v1/samples/by-specimen/{taxon_id}/{encoded_specimen_id}/related")

    assert resp.status_code == 200
    body = resp.json()
    assert body["specimen_id"] == specimen_id
    assert body["samples"][0]["sample"]["specimen_id"] == specimen_id
