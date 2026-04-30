"""Tests for assembly helper functions."""

from unittest.mock import Mock

import pytest
import yaml

from app.models.experiment import Experiment
from app.models.organism import Organism
from app.models.read import Read
from app.schemas.assembly import AssemblyDataTypes
from app.services.assembly_helper import (
    determine_assembly_data_types,
    generate_assembly_manifest,
    get_detected_platforms,
)


class TestDetermineAssemblyDataTypes:
    """Tests for determine_assembly_data_types function."""

    def test_pacbio_only(self):
        """Test detection of PacBio SMRT only."""
        experiments = [
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
        ]
        result = determine_assembly_data_types(experiments)
        assert result == AssemblyDataTypes.PACBIO_SMRT

    def test_oxford_nanopore_only(self):
        """Test detection of Oxford Nanopore only."""
        experiments = [
            Mock(platform="OXFORD_NANOPORE", library_strategy="WGS"),
        ]
        result = determine_assembly_data_types(experiments)
        assert result == AssemblyDataTypes.OXFORD_NANOPORE

    def test_illumina_hic(self):
        """Test that Illumina-only raises error (no long-read platform)."""
        experiments = [
            Mock(platform="ILLUMINA", library_strategy="Hi-C"),
        ]
        with pytest.raises(ValueError, match="No valid sequencing platforms detected"):
            determine_assembly_data_types(experiments)

    def test_illumina_wgs_treated_as_hic(self):
        """Test that ILLUMINA + WGS is treated as Hi-C."""
        experiments = [
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
            Mock(platform="ILLUMINA", library_strategy="WGS"),
        ]
        result = determine_assembly_data_types(experiments)
        assert result == AssemblyDataTypes.PACBIO_SMRT_HIC

    def test_pacbio_and_hic(self):
        """Test detection of PacBio + Hi-C combination."""
        experiments = [
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
            Mock(platform="ILLUMINA", library_strategy="Hi-C"),
        ]
        result = determine_assembly_data_types(experiments)
        assert result == AssemblyDataTypes.PACBIO_SMRT_HIC

    def test_nanopore_and_hic(self):
        """Test detection of Oxford Nanopore + Hi-C combination."""
        experiments = [
            Mock(platform="OXFORD_NANOPORE", library_strategy="WGS"),
            Mock(platform="ILLUMINA", library_strategy="WGS"),
        ]
        result = determine_assembly_data_types(experiments)
        assert result == AssemblyDataTypes.OXFORD_NANOPORE_HIC

    def test_pacbio_and_nanopore(self):
        """Test detection of PacBio + Oxford Nanopore combination."""
        experiments = [
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
            Mock(platform="OXFORD_NANOPORE", library_strategy="WGS"),
        ]
        result = determine_assembly_data_types(experiments)
        assert result == AssemblyDataTypes.PACBIO_SMRT_OXFORD_NANOPORE

    def test_all_three_platforms(self):
        """Test detection of all three platform types."""
        experiments = [
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
            Mock(platform="OXFORD_NANOPORE", library_strategy="WGS"),
            Mock(platform="ILLUMINA", library_strategy="Hi-C"),
        ]
        result = determine_assembly_data_types(experiments)
        assert result == AssemblyDataTypes.PACBIO_SMRT_OXFORD_NANOPORE_HIC

    def test_case_insensitive_platform(self):
        """Test that platform detection is case-insensitive."""
        experiments = [
            Mock(platform="pacbio_smrt", library_strategy="WGS"),
        ]
        result = determine_assembly_data_types(experiments)
        assert result == AssemblyDataTypes.PACBIO_SMRT

    def test_case_insensitive_library_strategy(self):
        """Test that library strategy detection is case-insensitive."""
        experiments = [
            Mock(platform="OXFORD_NANOPORE", library_strategy="WGS"),
            Mock(platform="ILLUMINA", library_strategy="wgs"),
        ]
        result = determine_assembly_data_types(experiments)
        assert result == AssemblyDataTypes.OXFORD_NANOPORE_HIC

    def test_no_valid_platforms_raises_error(self):
        """Test that no valid platforms raises ValueError."""
        experiments = [
            Mock(platform="UNKNOWN", library_strategy="WGS"),
        ]
        with pytest.raises(ValueError, match="No valid sequencing platforms detected"):
            determine_assembly_data_types(experiments)

    def test_empty_experiments_raises_error(self):
        """Test that empty experiments list raises ValueError."""
        with pytest.raises(ValueError, match="No valid sequencing platforms detected"):
            determine_assembly_data_types([])

    def test_none_platform_ignored(self):
        """Test that experiments with None platform are ignored."""
        experiments = [
            Mock(platform=None, library_strategy="WGS"),
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
        ]
        result = determine_assembly_data_types(experiments)
        assert result == AssemblyDataTypes.PACBIO_SMRT


class TestGetDetectedPlatforms:
    """Tests for get_detected_platforms function."""

    def test_single_platform(self):
        """Test detection of single platform."""
        experiments = [
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
        ]
        result = get_detected_platforms(experiments)
        assert result["platforms"] == ["PACBIO_SMRT"]
        assert result["library_strategies"] == ["WGS"]
        assert result["experiment_count"] == 1

    def test_multiple_platforms(self):
        """Test detection of multiple platforms."""
        experiments = [
            Mock(platform="PACBIO_SMRT", library_strategy="WGS"),
            Mock(platform="ILLUMINA", library_strategy="Hi-C"),
        ]
        result = get_detected_platforms(experiments)
        assert set(result["platforms"]) == {"PACBIO_SMRT", "ILLUMINA"}
        assert set(result["library_strategies"]) == {"WGS", "Hi-C"}
        assert result["experiment_count"] == 2

    def test_empty_experiments(self):
        """Test with empty experiments list."""
        result = get_detected_platforms([])
        assert result["platforms"] == []
        assert result["library_strategies"] == []
        assert result["experiment_count"] == 0


def _make_pacbio_experiment(
    exp_id="exp1", bpa_package_id="pkg-001", sample_id="sample-uuid-1", bioplatforms_base_url=None
):
    return Mock(
        id=exp_id,
        platform="PACBIO_SMRT",
        library_strategy="WGS",
        bpa_package_id=bpa_package_id,
        bioplatforms_base_url=bioplatforms_base_url,
        sample_id=sample_id,
    )


def _make_hic_experiment(
    exp_id="exp2", bpa_package_id="pkg-002", sample_id="sample-uuid-2", bioplatforms_base_url=None
):
    return Mock(
        id=exp_id,
        platform="ILLUMINA",
        library_strategy="Hi-C",
        bpa_package_id=bpa_package_id,
        bioplatforms_base_url=bioplatforms_base_url,
        sample_id=sample_id,
    )


class TestGenerateAssemblyManifest:
    """Tests for generate_assembly_manifest function."""

    def test_pacbio_reads_filtered_by_extension(self):
        """Test that only .ccs.bam and hifi_reads.bam files are included for PacBio."""
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

        result = generate_assembly_manifest(organism, reads, experiments, "tol1", 1)
        data = yaml.safe_load(result)

        pacbio = data["reads"]["PACBIO_SMRT"]
        assert "pkg-001" in pacbio
        resources = pacbio["pkg-001"]["resources"]
        urls = [r["url"] for r in resources]
        assert "https://example.com/1" in urls
        assert "https://example.com/2" in urls
        assert "https://example.com/3" not in urls
        assert all("md5sum" in r for r in resources)
        assert all("file_name" not in r for r in resources)

    def test_hic_reads_include_metadata(self):
        """Test that Hi-C reads include lane_number and are split by r1/r2."""
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

        result = generate_assembly_manifest(organism, reads, experiments, "tol1", 1)
        data = yaml.safe_load(result)

        hic = data["reads"]["Hi-C"]
        assert "pkg-002" in hic
        r1_resources = hic["pkg-002"]["resources"]["r1"]
        assert len(r1_resources) == 1
        assert r1_resources[0]["lane_number"] == "001"
        assert r1_resources[0]["md5sum"] == "abc123"

    def test_hic_reads_split_into_r1_r2(self):
        """Test that Hi-C reads with read_number 1 and 2 are split into r1 and r2."""
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

        result = generate_assembly_manifest(organism, reads, experiments, "tol1", 1)
        data = yaml.safe_load(result)

        resources = data["reads"]["Hi-C"]["pkg-002"]["resources"]
        assert len(resources["r1"]) == 1
        assert len(resources["r2"]) == 1
        assert resources["r1"][0]["url"] == "https://example.com/r1"
        assert resources["r2"][0]["url"] == "https://example.com/r2"

    def test_wgs_treated_as_hic(self):
        """Test that ILLUMINA + WGS is treated as Hi-C."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [
            Mock(
                id="exp1",
                platform="ILLUMINA",
                library_strategy="WGS",
                bpa_package_id="pkg-wgs",
                bioplatforms_base_url=None,
                sample_id="s1",
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

        result = generate_assembly_manifest(organism, reads, experiments, "tol1", 1)
        data = yaml.safe_load(result)

        assert "Hi-C" in data["reads"]
        assert "pkg-wgs" in data["reads"]["Hi-C"]

    def test_empty_reads_dict(self):
        """Test that empty reads result in empty reads dict."""
        organism = Mock(scientific_name="Test Species", taxon_id=12345)
        experiments = [
            Mock(
                id="exp1",
                platform="UNKNOWN",
                library_strategy="WGS",
                bpa_package_id="pkg-x",
                bioplatforms_base_url=None,
                sample_id="s1",
            )
        ]
        reads = []

        result = generate_assembly_manifest(organism, reads, experiments, "tol1", 1)

        assert "reads: {}" in result

    def test_organism_metadata_included(self):
        """Test that organism metadata is included in manifest."""
        organism = Mock(scientific_name="Saiphos equalis", taxon_id=172942)
        experiments = []
        reads = []

        result = generate_assembly_manifest(organism, reads, experiments, "tol123", 2)

        assert "scientific_name: Saiphos equalis" in result
        assert "taxon_id: 172942" in result
        assert "tolid: tol123" in result
        assert "version: 2" in result

    def test_sample_metadata_included_at_package_level(self):
        """Test that sample metadata appears at the bpa_package_id level."""
        organism = Mock(scientific_name="Saiphos equalis", taxon_id=172942)
        experiments = [
            Mock(
                id="exp1",
                sample_id="550e8400-e29b-41d4-a716-446655440000",
                platform="PACBIO_SMRT",
                library_strategy="WGS",
                bpa_package_id="pkg-001",
                bioplatforms_base_url=None,
            )
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
            )
        ]
        sample_metadata_by_id = {
            "550e8400-e29b-41d4-a716-446655440000": {
                "bpa_sample_id": "102.100.100/9000",
                "specimen_id": "SPEC-001",
            }
        }

        result = generate_assembly_manifest(
            organism, reads, experiments, "tol123", 2, sample_metadata_by_id
        )
        data = yaml.safe_load(result)

        pkg = data["reads"]["PACBIO_SMRT"]["pkg-001"]
        assert pkg["sample_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert pkg["bpa_sample_id"] == "102.100.100/9000"
        assert pkg["specimen_id"] == "SPEC-001"

    def test_bioplatforms_base_url_included_when_set(self):
        """Test that bioplatforms_base_url appears in the manifest when set on the experiment."""
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

        result = generate_assembly_manifest(organism, reads, experiments, "tol1", 1)
        data = yaml.safe_load(result)

        pkg = data["reads"]["PACBIO_SMRT"]["pkg-001"]
        assert pkg["bioplatforms_base_url"] == "https://base.example.com/pkg-001"

    def test_bioplatforms_base_url_omitted_when_none(self):
        """Test that bioplatforms_base_url is absent from the manifest when not set."""
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

        result = generate_assembly_manifest(organism, reads, experiments, "tol1", 1)
        data = yaml.safe_load(result)

        pkg = data["reads"]["PACBIO_SMRT"]["pkg-001"]
        assert "bioplatforms_base_url" not in pkg

    def test_reads_without_experiment_id_skipped(self):
        """Test that reads without experiment_id are skipped."""
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

        result = generate_assembly_manifest(organism, reads, experiments, "tol1", 1)

        assert "reads: {}" in result

    def test_multiple_platform_types(self):
        """Test manifest with both PacBio and Hi-C packages."""
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

        result = generate_assembly_manifest(organism, reads, experiments, "tol1", 1)
        data = yaml.safe_load(result)

        assert "PACBIO_SMRT" in data["reads"]
        assert "Hi-C" in data["reads"]
        assert "pkg-pacbio" in data["reads"]["PACBIO_SMRT"]
        assert "pkg-hic" in data["reads"]["Hi-C"]

    def test_multiple_reads_same_package(self):
        """Test that multiple reads under the same experiment are grouped together."""
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

        result = generate_assembly_manifest(organism, reads, experiments, "tol1", 1)
        data = yaml.safe_load(result)

        resources = data["reads"]["PACBIO_SMRT"]["pkg-001"]["resources"]
        assert len(resources) == 2
