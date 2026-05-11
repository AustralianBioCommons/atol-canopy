"""Tests for assembly helper functions."""

from unittest.mock import Mock
from uuid import UUID

import pytest

from app.models.experiment import Experiment
from app.models.organism import Organism
from app.models.read import Read
from app.schemas.assembly import AssemblyDataTypes
from app.services.assembly_helper import (
    determine_assembly_data_types,
    generate_assembly_manifest_json,
    get_available_assembly_data_types,
    get_detected_platforms,
)

LONG_READ_SAMPLE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
HIC_SAMPLE_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
LONG_READ_SAMPLE_STR = str(LONG_READ_SAMPLE_ID)
HIC_SAMPLE_STR = str(HIC_SAMPLE_ID)


class TestDetermineAssemblyDataTypes:
    """Tests for determine_assembly_data_types function."""

    def test_pacbio_only(self):
        experiments = [Mock(platform="PACBIO_SMRT", library_strategy="WGS")]
        assert determine_assembly_data_types(experiments) == AssemblyDataTypes.PACBIO_SMRT

    def test_oxford_nanopore_only(self):
        experiments = [Mock(platform="OXFORD_NANOPORE", library_strategy="WGS")]
        assert determine_assembly_data_types(experiments) == AssemblyDataTypes.OXFORD_NANOPORE

    def test_illumina_hic_alone_raises_error(self):
        experiments = [Mock(platform="ILLUMINA", library_strategy="Hi-C")]
        with pytest.raises(ValueError, match="No valid data types detected in experiments"):
            determine_assembly_data_types(experiments)

    def test_illumina_wgs_not_treated_as_hic(self):
        experiments = [
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
            Mock(platform="ILLUMINA", library_strategy="WGS"),
        ]
        assert determine_assembly_data_types(experiments) == AssemblyDataTypes.PACBIO_SMRT

    def test_pacbio_and_hic(self):
        experiments = [
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
            Mock(platform="ILLUMINA", library_strategy="Hi-C"),
        ]
        assert determine_assembly_data_types(experiments) == AssemblyDataTypes.PACBIO_SMRT_HIC

    def test_nanopore_and_hic(self):
        experiments = [
            Mock(platform="OXFORD_NANOPORE", library_strategy="WGS"),
            Mock(platform="ILLUMINA", library_strategy="Hi-C"),
        ]
        assert determine_assembly_data_types(experiments) == AssemblyDataTypes.OXFORD_NANOPORE_HIC

    def test_pacbio_and_nanopore(self):
        experiments = [
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
            Mock(platform="OXFORD_NANOPORE", library_strategy="WGS"),
        ]
        assert (
            determine_assembly_data_types(experiments)
            == AssemblyDataTypes.PACBIO_SMRT_OXFORD_NANOPORE
        )

    def test_all_three_platforms(self):
        experiments = [
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
            Mock(platform="OXFORD_NANOPORE", library_strategy="WGS"),
            Mock(platform="ILLUMINA", library_strategy="Hi-C"),
        ]
        assert (
            determine_assembly_data_types(experiments)
            == AssemblyDataTypes.PACBIO_SMRT_OXFORD_NANOPORE_HIC
        )

    def test_case_insensitive_platform(self):
        experiments = [Mock(platform="pacbio_smrt", library_strategy="WGS")]
        assert determine_assembly_data_types(experiments) == AssemblyDataTypes.PACBIO_SMRT

    def test_case_insensitive_library_strategy(self):
        experiments = [
            Mock(platform="OXFORD_NANOPORE", library_strategy="WGS"),
            Mock(platform="ILLUMINA", library_strategy="hi-c"),
        ]
        assert determine_assembly_data_types(experiments) == AssemblyDataTypes.OXFORD_NANOPORE_HIC

    def test_no_valid_platforms_raises_error(self):
        experiments = [Mock(platform="UNKNOWN", library_strategy="WGS")]
        with pytest.raises(ValueError, match="No valid data types detected in experiments"):
            determine_assembly_data_types(experiments)

    def test_empty_experiments_raises_error(self):
        with pytest.raises(ValueError, match="No valid data types detected in experiments"):
            determine_assembly_data_types([])

    def test_none_platform_ignored(self):
        experiments = [
            Mock(platform=None, library_strategy="WGS"),
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
        ]
        assert determine_assembly_data_types(experiments) == AssemblyDataTypes.PACBIO_SMRT


class TestGetAvailableAssemblyDataTypes:
    """Tests for discovery-oriented assembly data type detection."""

    def test_hic_only_is_reported_for_discovery(self):
        experiments = [Mock(platform="ILLUMINA", library_strategy="Hi-C")]
        assert get_available_assembly_data_types(experiments) == ["Hi-C"]

    def test_returns_atomic_data_types_in_stable_order(self):
        experiments = [
            Mock(platform="ILLUMINA", library_strategy="Hi-C"),
            Mock(platform="OXFORD_NANOPORE", library_strategy="WGS"),
            Mock(platform="PACBIO_SMRT", library_strategy="WGA"),
        ]
        assert get_available_assembly_data_types(experiments) == [
            "PACBIO_SMRT",
            "OXFORD_NANOPORE",
            "Hi-C",
        ]

    def test_ignores_non_assembly_illumina_wgs(self):
        experiments = [Mock(platform="ILLUMINA", library_strategy="WGS")]
        assert get_available_assembly_data_types(experiments) == []

    def test_rnaseq_is_reported_for_discovery(self):
        experiments = [Mock(platform="ILLUMINA", library_strategy="RNA-Seq")]
        assert get_available_assembly_data_types(experiments) == ["RNA-Seq"]


class TestGetDetectedPlatforms:
    """Tests for get_detected_platforms function."""

    def test_single_platform(self):
        experiments = [Mock(platform="PACBIO_SMRT", library_strategy="WGS")]
        result = get_detected_platforms(experiments)
        assert result["platforms"] == ["PACBIO_SMRT"]
        assert result["library_strategies"] == ["WGS"]
        assert result["experiment_count"] == 1

    def test_multiple_platforms(self):
        experiments = [
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
            Mock(platform="ILLUMINA", library_strategy="Hi-C"),
        ]
        result = get_detected_platforms(experiments)
        assert set(result["platforms"]) == {"PACBIO_SMRT", "ILLUMINA"}
        assert set(result["library_strategies"]) == {"WGS", "Hi-C"}
        assert result["experiment_count"] == 2

    def test_empty_experiments(self):
        result = get_detected_platforms([])
        assert result["platforms"] == []
        assert result["library_strategies"] == []
        assert result["experiment_count"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# Helpers for building mock experiments / reads
# ──────────────────────────────────────────────────────────────────────────────


def _make_pacbio_experiment(
    exp_id="exp1",
    bpa_package_id="pkg-001",
    sample_id=LONG_READ_SAMPLE_STR,
    bioplatforms_base_url=None,
):
    return Mock(
        id=exp_id,
        platform="PACBIO_SMRT",
        library_strategy="WGS",
        bpa_package_id=bpa_package_id,
        bioplatforms_base_url=bioplatforms_base_url,
        sample_id=sample_id,
    )


def _make_ont_experiment(
    exp_id="exp-ont",
    bpa_package_id="pkg-ont",
    sample_id=LONG_READ_SAMPLE_STR,
    bioplatforms_base_url=None,
):
    return Mock(
        id=exp_id,
        platform="OXFORD_NANOPORE",
        library_strategy="WGS",
        bpa_package_id=bpa_package_id,
        bioplatforms_base_url=bioplatforms_base_url,
        sample_id=sample_id,
    )


def _make_hic_experiment(
    exp_id="exp2",
    bpa_package_id="pkg-002",
    sample_id=HIC_SAMPLE_STR,
    bioplatforms_base_url=None,
):
    return Mock(
        id=exp_id,
        platform="ILLUMINA",
        library_strategy="Hi-C",
        bpa_package_id=bpa_package_id,
        bioplatforms_base_url=bioplatforms_base_url,
        sample_id=sample_id,
    )


class TestGenerateAssemblyManifestJson:
    """Tests for generate_assembly_manifest_json function."""

    # ── PacBio ────────────────────────────────────────────────────────────────

    def test_pacbio_reads_filtered_by_extension(self):
        """Only .ccs.bam and hifi_reads.bam files are included for PacBio."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [_make_pacbio_experiment()]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp1",
                file_name="sample.ccs.bam",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/1",
                read_number=None,
                lane_number=None,
            ),
            Mock(
                id="r2",
                experiment_id="exp1",
                file_name="sample.hifi_reads.bam",
                file_checksum="def456",
                bioplatforms_url="https://example.com/2",
                read_number=None,
                lane_number=None,
            ),
            Mock(
                id="r3",
                experiment_id="exp1",
                file_name="sample.subreads.bam",
                file_checksum="ghi789",
                bioplatforms_url="https://example.com/3",
                read_number=None,
                lane_number=None,
            ),
        ]

        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID
        )

        pacbio = result["reads"]["PACBIO_SMRT"]
        assert "pkg-001" in pacbio
        resources = pacbio["pkg-001"]["resources"]
        urls = [r["url"] for r in resources]
        assert "https://example.com/1" in urls
        assert "https://example.com/2" in urls
        assert "https://example.com/3" not in urls
        assert all("md5sum" in r for r in resources)

    def test_pacbio_read_without_file_name_skipped(self):
        """PacBio reads with no file_name are silently skipped."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [_make_pacbio_experiment()]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp1",
                file_name=None,
                file_checksum="abc123",
                bioplatforms_url="https://example.com/1",
                read_number=None,
                lane_number=None,
            ),
        ]

        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID
        )
        assert result["reads"] == {}

    # ── Oxford Nanopore ───────────────────────────────────────────────────────

    def test_ont_reads_included_without_extension_filter(self):
        """All ONT reads are included regardless of file extension."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [_make_ont_experiment()]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp-ont",
                file_name="sample.fastq.gz",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/ont1",
                read_number=None,
                lane_number=None,
            ),
            Mock(
                id="r2",
                experiment_id="exp-ont",
                file_name="sample.pod5",
                file_checksum="def456",
                bioplatforms_url="https://example.com/ont2",
                read_number=None,
                lane_number=None,
            ),
        ]

        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID
        )

        assert "OXFORD_NANOPORE" in result["reads"]
        resources = result["reads"]["OXFORD_NANOPORE"]["pkg-ont"]["resources"]
        assert len(resources) == 2

    # ── Hi-C ─────────────────────────────────────────────────────────────────

    def test_hic_reads_include_metadata(self):
        """Hi-C reads include lane_number and are split by r1/r2."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [_make_hic_experiment()]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp2",
                file_name="hic_R1.fastq.gz",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/1",
                read_number="1",
                lane_number="001",
            ),
        ]

        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID, HIC_SAMPLE_ID
        )

        hic = result["reads"]["Hi-C"]
        assert "pkg-002" in hic
        r1_resources = hic["pkg-002"]["resources"]["r1"]
        assert len(r1_resources) == 1
        assert r1_resources[0]["lane_number"] == "001"
        assert r1_resources[0]["md5sum"] == "abc123"

    def test_hic_reads_split_into_r1_r2(self):
        """Hi-C reads with read_number 1 and 2 are split into r1 and r2."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [_make_hic_experiment()]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp2",
                file_name="hic_R1.fastq.gz",
                file_checksum="md5-r1",
                bioplatforms_url="https://example.com/r1",
                read_number="1",
                lane_number="L001",
            ),
            Mock(
                id="r2",
                experiment_id="exp2",
                file_name="hic_R2.fastq.gz",
                file_checksum="md5-r2",
                bioplatforms_url="https://example.com/r2",
                read_number="2",
                lane_number="L001",
            ),
        ]

        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID, HIC_SAMPLE_ID
        )

        resources = result["reads"]["Hi-C"]["pkg-002"]["resources"]
        assert len(resources["r1"]) == 1
        assert len(resources["r2"]) == 1
        assert resources["r1"][0]["url"] == "https://example.com/r1"
        assert resources["r2"][0]["url"] == "https://example.com/r2"

    def test_wgs_not_treated_as_hic(self):
        """ILLUMINA + WGS does not populate the Hi-C section."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [
            Mock(
                id="exp1",
                platform="ILLUMINA",
                library_strategy="WGS",
                bpa_package_id="pkg-wgs",
                bioplatforms_base_url=None,
                sample_id=HIC_SAMPLE_STR,
            )
        ]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp1",
                file_name="sample_R1.fastq.gz",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/1",
                read_number="1",
                lane_number="001",
            ),
        ]

        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID, HIC_SAMPLE_ID
        )

        assert "Hi-C" not in result["reads"]

    def test_hic_section_omitted_when_no_hic_sample_id(self):
        """Hi-C section is absent when hic_sample_id is not supplied."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [
            _make_pacbio_experiment(),
            _make_hic_experiment(),  # hic experiment present but hic_sample_id not passed
        ]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp1",
                file_name="sample.ccs.bam",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/1",
                read_number=None,
                lane_number=None,
            ),
            Mock(
                id="r2",
                experiment_id="exp2",
                file_name="hic_R1.fastq.gz",
                file_checksum="def456",
                bioplatforms_url="https://example.com/2",
                read_number="1",
                lane_number="001",
            ),
        ]

        # hic_sample_id is None → Hi-C section must be absent
        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID, hic_sample_id=None
        )

        assert "Hi-C" not in result["reads"]
        assert "PACBIO_SMRT" in result["reads"]

    def test_reads_routed_by_specimen_sample_not_platform(self):
        """Reads from long_read_sample_id are never placed in Hi-C even if ILLUMINA."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        # An ILLUMINA experiment that belongs to the long_read_specimen_sample_id
        experiments = [
            Mock(
                id="exp-ill",
                platform="ILLUMINA",
                library_strategy="WGS",
                bpa_package_id="pkg-ill",
                bioplatforms_base_url=None,
                sample_id=LONG_READ_SAMPLE_STR,  # belongs to long-read sample
            )
        ]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp-ill",
                file_name="sample_R1.fastq.gz",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/1",
                read_number="1",
                lane_number="001",
            ),
        ]

        # Illumina experiment on long-read sample → should NOT appear in Hi-C section
        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID, HIC_SAMPLE_ID
        )

        assert result["reads"] == {}

    # ── Mixed long-read + Hi-C ────────────────────────────────────────────────

    def test_multiple_platform_types(self):
        """Manifest with PacBio (long-read sample) and Hi-C (hic sample) packages."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [
            _make_pacbio_experiment(exp_id="exp1", bpa_package_id="pkg-pacbio"),
            _make_hic_experiment(exp_id="exp2", bpa_package_id="pkg-hic"),
        ]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp1",
                file_name="sample.ccs.bam",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/1",
                read_number=None,
                lane_number=None,
            ),
            Mock(
                id="r2",
                experiment_id="exp2",
                file_name="hic_R1.fastq.gz",
                file_checksum="def456",
                bioplatforms_url="https://example.com/2",
                read_number="1",
                lane_number="001",
            ),
        ]

        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID, HIC_SAMPLE_ID
        )

        assert "PACBIO_SMRT" in result["reads"]
        assert "Hi-C" in result["reads"]
        assert "pkg-pacbio" in result["reads"]["PACBIO_SMRT"]
        assert "pkg-hic" in result["reads"]["Hi-C"]

    def test_same_specimen_sample_can_supply_long_reads_and_hic(self):
        """When the same specimen sample ID is used for both roles, both sections are populated."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [
            _make_pacbio_experiment(
                exp_id="exp-pb",
                bpa_package_id="pkg-pacbio",
                sample_id=LONG_READ_SAMPLE_STR,
            ),
            _make_hic_experiment(
                exp_id="exp-hic",
                bpa_package_id="pkg-hic",
                sample_id=LONG_READ_SAMPLE_STR,
            ),
        ]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp-pb",
                file_name="sample.ccs.bam",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/pb",
                read_number=None,
                lane_number=None,
            ),
            Mock(
                id="r2",
                experiment_id="exp-hic",
                file_name="hic_R1.fastq.gz",
                file_checksum="def456",
                bioplatforms_url="https://example.com/hic",
                read_number="1",
                lane_number="001",
            ),
        ]

        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID, LONG_READ_SAMPLE_ID
        )

        assert "PACBIO_SMRT" in result["reads"]
        assert "Hi-C" in result["reads"]

    def test_derived_sample_reads_are_attributed_to_parent_specimen(self):
        """Reads from derived sequencing samples are routed to the selected parent specimen."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        derived_sample_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        experiments = [
            _make_pacbio_experiment(
                exp_id="exp-derived",
                bpa_package_id="pkg-derived",
                sample_id=derived_sample_id,
            ),
        ]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp-derived",
                file_name="sample.ccs.bam",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/pb",
                read_number=None,
                lane_number=None,
            ),
        ]
        sample_metadata_by_id = {
            LONG_READ_SAMPLE_STR: {
                "bpa_sample_id": "102.100.100/9000",
                "specimen_id": "SPEC-001",
            }
        }

        result = generate_assembly_manifest_json(
            organism,
            reads,
            experiments,
            "tol1",
            1,
            LONG_READ_SAMPLE_ID,
            sample_metadata_by_id=sample_metadata_by_id,
            sequencing_sample_to_specimen_sample_id={
                derived_sample_id: LONG_READ_SAMPLE_STR,
            },
        )

        pkg = result["reads"]["PACBIO_SMRT"]["pkg-derived"]
        assert pkg["sample_id"] == LONG_READ_SAMPLE_STR
        assert pkg["specimen_id"] == "SPEC-001"

    def test_pacbio_and_ont_in_same_long_read_sample(self):
        """Both PacBio and ONT reads from the same long-read specimen appear in separate sections."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [
            _make_pacbio_experiment(exp_id="exp-pb", bpa_package_id="pkg-pb"),
            _make_ont_experiment(exp_id="exp-ont", bpa_package_id="pkg-ont"),
        ]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp-pb",
                file_name="sample.ccs.bam",
                file_checksum="abc",
                bioplatforms_url="https://example.com/pb",
                read_number=None,
                lane_number=None,
            ),
            Mock(
                id="r2",
                experiment_id="exp-ont",
                file_name="sample.fastq.gz",
                file_checksum="def",
                bioplatforms_url="https://example.com/ont",
                read_number=None,
                lane_number=None,
            ),
        ]

        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID
        )

        assert "PACBIO_SMRT" in result["reads"]
        assert "OXFORD_NANOPORE" in result["reads"]

    # ── Metadata ──────────────────────────────────────────────────────────────

    def test_empty_reads_dict(self):
        """Empty reads result in an empty reads section."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        result = generate_assembly_manifest_json(organism, [], [], "tol1", 1, LONG_READ_SAMPLE_ID)
        assert result["reads"] == {}

    def test_organism_metadata_included(self):
        """Organism metadata is present in the manifest."""
        organism = Mock(scientific_name="Saiphos equalis", taxon_id=172942)
        result = generate_assembly_manifest_json(organism, [], [], "tol123", 2, LONG_READ_SAMPLE_ID)
        assert result["scientific_name"] == "Saiphos equalis"
        assert result["taxon_id"] == 172942
        assert result["tolid"] == "tol123"
        assert result["version"] == 2

    def test_sample_metadata_included_at_package_level(self):
        """Sample metadata (bpa_sample_id, specimen_id) appears at the package level."""
        organism = Mock(scientific_name="Saiphos equalis", taxon_id=172942)
        experiments = [_make_pacbio_experiment()]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp1",
                file_name="sample.ccs.bam",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/1",
                read_number=None,
                lane_number=None,
            )
        ]
        sample_metadata_by_id = {
            LONG_READ_SAMPLE_STR: {
                "bpa_sample_id": "102.100.100/9000",
                "specimen_id": "SPEC-001",
            }
        }

        result = generate_assembly_manifest_json(
            organism,
            reads,
            experiments,
            "tol123",
            2,
            LONG_READ_SAMPLE_ID,
            sample_metadata_by_id=sample_metadata_by_id,
        )

        pkg = result["reads"]["PACBIO_SMRT"]["pkg-001"]
        assert pkg["sample_id"] == LONG_READ_SAMPLE_STR
        assert pkg["bpa_sample_id"] == "102.100.100/9000"
        assert pkg["specimen_id"] == "SPEC-001"

    def test_bioplatforms_base_url_included_when_set(self):
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [
            _make_pacbio_experiment(bioplatforms_base_url="https://base.example.com/pkg-001")
        ]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp1",
                file_name="sample.ccs.bam",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/1",
                read_number=None,
                lane_number=None,
            ),
        ]

        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID
        )
        pkg = result["reads"]["PACBIO_SMRT"]["pkg-001"]
        assert pkg["bioplatforms_base_url"] == "https://base.example.com/pkg-001"

    def test_bioplatforms_base_url_omitted_when_none(self):
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [_make_pacbio_experiment(bioplatforms_base_url=None)]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp1",
                file_name="sample.ccs.bam",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/1",
                read_number=None,
                lane_number=None,
            ),
        ]

        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID
        )
        pkg = result["reads"]["PACBIO_SMRT"]["pkg-001"]
        assert "bioplatforms_base_url" not in pkg

    def test_reads_without_experiment_id_skipped(self):
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [_make_pacbio_experiment()]
        reads = [
            Mock(
                id="r1",
                experiment_id=None,
                file_name="sample.ccs.bam",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/1",
                read_number=None,
                lane_number=None,
            ),
        ]

        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID
        )
        assert result["reads"] == {}

    def test_multiple_reads_same_package(self):
        """Multiple reads under the same experiment are grouped together."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [_make_pacbio_experiment()]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp1",
                file_name="sample1.ccs.bam",
                file_checksum="md5-1",
                bioplatforms_url="https://example.com/1",
                read_number=None,
                lane_number=None,
            ),
            Mock(
                id="r2",
                experiment_id="exp1",
                file_name="sample2.ccs.bam",
                file_checksum="md5-2",
                bioplatforms_url="https://example.com/2",
                read_number=None,
                lane_number=None,
            ),
        ]

        result = generate_assembly_manifest_json(
            organism, reads, experiments, "tol1", 1, LONG_READ_SAMPLE_ID
        )
        resources = result["reads"]["PACBIO_SMRT"]["pkg-001"]["resources"]
        assert len(resources) == 2

    def test_manifest_is_dict_not_string(self):
        """generate_assembly_manifest_json returns a dict, not a YAML/JSON string."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        result = generate_assembly_manifest_json(organism, [], [], "tol1", 1, LONG_READ_SAMPLE_ID)
        assert isinstance(result, dict)
        assert "reads" in result
