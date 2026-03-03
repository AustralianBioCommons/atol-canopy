"""Tests for assembly helper functions."""

from unittest.mock import Mock

import pytest

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


class TestGenerateAssemblyManifest:
    """Tests for generate_assembly_manifest function."""

    def test_pacbio_reads_filtered_by_extension(self):
        """Test that only .ccs.bam and hifi_reads.bam files are included for PacBio."""
        organism = Mock(scientific_name="Test Species", tax_id=12345)
        experiments = [Mock(id="exp1", platform="PACBIO_SMRT", library_strategy="WGS")]
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

        assert "PACBIO_SMRT:" in result
        assert "sample.ccs.bam" in result
        assert "sample.hifi_reads.bam" in result
        assert "sample.subreads.bam" not in result

    def test_hic_reads_include_metadata(self):
        """Test that Hi-C reads include read_number and lane_number."""
        organism = Mock(scientific_name="Test Species", tax_id=12345)
        experiments = [Mock(id="exp1", platform="ILLUMINA", library_strategy="Hi-C")]
        reads = [
            Mock(
                id="r1",
                experiment_id="exp1",
                file_name="hic_R1.fastq.gz",
                file_checksum="abc123",
                bioplatforms_url="https://example.com/1",
                read_number="1",
                lane_number="001",
            ),
        ]

        result = generate_assembly_manifest(organism, reads, experiments, "tol1", 1)

        assert "Hi-C:" in result
        assert "hic_R1.fastq.gz" in result
        assert "read_number: '1'" in result
        assert "lane_number: '001'" in result

    def test_wgs_treated_as_hic(self):
        """Test that ILLUMINA + WGS is treated as Hi-C."""
        organism = Mock(scientific_name="Test Species", tax_id=12345)
        experiments = [Mock(id="exp1", platform="ILLUMINA", library_strategy="WGS")]
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

        assert "Hi-C:" in result
        assert "sample_R1.fastq.gz" in result

    def test_empty_reads_dict(self):
        """Test that empty reads result in empty reads dict."""
        organism = Mock(scientific_name="Test Species", tax_id=12345)
        experiments = [Mock(id="exp1", platform="UNKNOWN", library_strategy="WGS")]
        reads = []

        result = generate_assembly_manifest(organism, reads, experiments, "tol1", 1)

        assert "reads: {}" in result

    def test_organism_metadata_included(self):
        """Test that organism metadata is included in manifest."""
        organism = Mock(scientific_name="Saiphos equalis", tax_id=172942)
        experiments = []
        reads = []

        result = generate_assembly_manifest(organism, reads, experiments, "tol123", 2)

        assert "scientific_name: Saiphos equalis" in result
        assert "taxon_id: 172942" in result
        assert "tolid: tol123" in result
        assert "version: 2" in result

    def test_reads_without_experiment_id_skipped(self):
        """Test that reads without experiment_id are skipped."""
        organism = Mock(scientific_name="Test Species", tax_id=12345)
        experiments = [Mock(id="exp1", platform="PACBIO_SMRT", library_strategy="WGS")]
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

        assert "sample.ccs.bam" not in result
        assert "reads: {}" in result

    def test_multiple_platform_types(self):
        """Test manifest with both PacBio and Hi-C reads."""
        organism = Mock(scientific_name="Test Species", tax_id=12345)
        experiments = [
            Mock(id="exp1", platform="PACBIO_SMRT", library_strategy="WGS"),
            Mock(id="exp2", platform="ILLUMINA", library_strategy="Hi-C"),
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

        assert "PACBIO_SMRT:" in result
        assert "Hi-C:" in result
        assert "sample.ccs.bam" in result
        assert "hic_R1.fastq.gz" in result
