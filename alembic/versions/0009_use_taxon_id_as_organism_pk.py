"""Use organism.taxon_id as the primary key and FK target.

Revision ID: 0009_use_taxon_id_as_organism_pk
Revises: 0008_add_base_url_to_experiment
Create Date: 2026-04-30 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0009_use_taxon_id_as_organism_pk"
down_revision = "0008_add_base_url_to_experiment"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE organism RENAME COLUMN tax_id TO taxon_id")

    # Rename base_url to bioplatforms_base_url in experiment table (merged from 0010)
    op.alter_column("experiment", "base_url", new_column_name="bioplatforms_base_url")

    op.drop_index("uq_one_project_type_per_organism", table_name="project")
    op.drop_index("uq_specimen_per_organism_specimen_id", table_name="sample")
    op.drop_index("idx_sample_organism_specimen_lookup", table_name="sample")
    op.drop_index("idx_sample_organism_key", table_name="sample")
    op.drop_index("idx_assembly_version_key", table_name="assembly")
    op.drop_index("idx_assembly_organism_key", table_name="assembly")
    op.drop_index("idx_genome_note_organism_key", table_name="genome_note")
    op.drop_index("idx_genome_note_published", table_name="genome_note")
    op.drop_index("uq_genome_note_one_published_per_organism", table_name="genome_note")
    op.drop_index("idx_tax_id", table_name="organism")

    _drop_legacy_fk_constraints()
    op.execute("ALTER TABLE organism DROP CONSTRAINT IF EXISTS organism_pkey")
    op.execute("ALTER TABLE organism ADD CONSTRAINT organism_pkey PRIMARY KEY (taxon_id)")

    _migrate_fk_column("project", nullable=False)
    _migrate_fk_column("sample", nullable=False)
    _migrate_fk_column("submission_attempt", nullable=True)
    _migrate_fk_column("assembly", nullable=False)
    _migrate_fk_column("assembly_run", nullable=False)
    _migrate_fk_column("genome_note", nullable=False)

    op.execute("ALTER TABLE genome_note DROP CONSTRAINT IF EXISTS uq_genome_note_organism_version")
    op.create_unique_constraint(
        "uq_genome_note_organism_version", "genome_note", ["taxon_id", "version"]
    )

    op.create_index(
        "uq_one_project_type_per_organism", "project", ["taxon_id", "project_type"], unique=True
    )
    op.create_index(
        "uq_specimen_per_organism_specimen_id",
        "sample",
        ["taxon_id", "specimen_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'specimen' AND specimen_id IS NOT NULL"),
    )
    op.create_index(
        "idx_sample_organism_specimen_lookup",
        "sample",
        ["taxon_id", "specimen_id"],
        postgresql_where=sa.text("specimen_id IS NOT NULL"),
    )
    op.create_index("idx_sample_taxon_id", "sample", ["taxon_id"])
    op.create_index(
        "idx_assembly_version_key", "assembly", ["data_types", "taxon_id", "sample_id", "version"]
    )
    op.create_index("idx_assembly_taxon_id", "assembly", ["taxon_id"])
    op.create_index("idx_genome_note_taxon_id", "genome_note", ["taxon_id"])
    op.create_index(
        "idx_genome_note_published",
        "genome_note",
        ["taxon_id", "is_published"],
        postgresql_where=sa.text("is_published = TRUE"),
    )
    op.create_index(
        "uq_genome_note_one_published_per_organism",
        "genome_note",
        ["taxon_id"],
        unique=True,
        postgresql_where=sa.text("is_published = TRUE"),
    )
    op.drop_column("organism", "grouping_key")


def downgrade():
    op.add_column("organism", sa.Column("grouping_key", sa.Text(), nullable=True))
    op.execute("UPDATE organism SET grouping_key = CAST(taxon_id AS TEXT)")
    op.alter_column("organism", "grouping_key", nullable=False)
    op.create_unique_constraint("organism_grouping_key_key", "organism", ["grouping_key"])

    op.drop_index("uq_genome_note_one_published_per_organism", table_name="genome_note")
    op.drop_index("idx_genome_note_published", table_name="genome_note")
    op.drop_index("idx_genome_note_taxon_id", table_name="genome_note")
    op.drop_index("idx_assembly_taxon_id", table_name="assembly")
    op.drop_index("idx_assembly_version_key", table_name="assembly")
    op.drop_index("idx_sample_taxon_id", table_name="sample")
    op.drop_index("idx_sample_organism_specimen_lookup", table_name="sample")
    op.drop_index("uq_specimen_per_organism_specimen_id", table_name="sample")
    op.drop_index("uq_one_project_type_per_organism", table_name="project")

    op.execute("ALTER TABLE genome_note DROP CONSTRAINT IF EXISTS uq_genome_note_organism_version")

    _downgrade_fk_column("project", nullable=False)
    _downgrade_fk_column("sample", nullable=False)
    _downgrade_fk_column("submission_attempt", nullable=True)
    _downgrade_fk_column("assembly", nullable=False)
    _downgrade_fk_column("assembly_run", nullable=False)
    _downgrade_fk_column("genome_note", nullable=False)

    op.create_unique_constraint(
        "uq_genome_note_organism_version", "genome_note", ["organism_key", "version"]
    )

    op.create_index(
        "uq_one_project_type_per_organism", "project", ["organism_key", "project_type"], unique=True
    )
    op.create_index(
        "uq_specimen_per_organism_specimen_id",
        "sample",
        ["organism_key", "specimen_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'specimen' AND specimen_id IS NOT NULL"),
    )
    op.create_index(
        "idx_sample_organism_specimen_lookup",
        "sample",
        ["organism_key", "specimen_id"],
        postgresql_where=sa.text("specimen_id IS NOT NULL"),
    )
    op.create_index("idx_sample_organism_key", "sample", ["organism_key"])
    op.create_index(
        "idx_assembly_version_key",
        "assembly",
        ["data_types", "organism_key", "sample_id", "version"],
    )
    op.create_index("idx_assembly_organism_key", "assembly", ["organism_key"])
    op.create_index("idx_genome_note_organism_key", "genome_note", ["organism_key"])
    op.create_index(
        "idx_genome_note_published",
        "genome_note",
        ["organism_key", "is_published"],
        postgresql_where=sa.text("is_published = TRUE"),
    )
    op.create_index(
        "uq_genome_note_one_published_per_organism",
        "genome_note",
        ["organism_key"],
        unique=True,
        postgresql_where=sa.text("is_published = TRUE"),
    )
    op.create_index("idx_tax_id", "organism", ["tax_id"])

    op.execute("ALTER TABLE organism DROP CONSTRAINT IF EXISTS organism_pkey")
    op.execute("ALTER TABLE organism ADD CONSTRAINT organism_pkey PRIMARY KEY (grouping_key)")
    op.execute("ALTER TABLE organism RENAME COLUMN taxon_id TO tax_id")

    # Revert base_url rename (merged from 0010 downgrade)
    op.alter_column("experiment", "bioplatforms_base_url", new_column_name="base_url")


def _migrate_fk_column(table_name: str, *, nullable: bool) -> None:
    op.add_column(table_name, sa.Column("taxon_id", sa.Integer(), nullable=True))
    op.execute(
        f"""
        UPDATE {table_name} AS child
        SET taxon_id = organism.taxon_id
        FROM organism
        WHERE child.organism_key = organism.grouping_key
        """
    )
    op.execute(f"ALTER TABLE {table_name} DROP COLUMN organism_key")
    if not nullable:
        op.alter_column(table_name, "taxon_id", nullable=False)
    op.create_foreign_key(
        f"{table_name}_taxon_id_fkey",
        table_name,
        "organism",
        ["taxon_id"],
        ["taxon_id"],
        ondelete="CASCADE" if table_name != "submission_attempt" else "RESTRICT",
    )


def _drop_legacy_fk_constraints() -> None:
    for table_name in (
        "project",
        "sample",
        "submission_attempt",
        "assembly",
        "assembly_run",
        "genome_note",
    ):
        op.drop_constraint(
            f"{table_name}_organism_key_fkey",
            table_name,
            type_="foreignkey",
        )


def _downgrade_fk_column(table_name: str, *, nullable: bool) -> None:
    op.add_column(table_name, sa.Column("organism_key", sa.Text(), nullable=True))
    op.execute(
        f"""
        UPDATE {table_name} AS child
        SET organism_key = organism.grouping_key
        FROM organism
        WHERE child.taxon_id = organism.taxon_id
        """
    )
    op.execute(f"ALTER TABLE {table_name} DROP COLUMN taxon_id")
    if not nullable:
        op.alter_column(table_name, "organism_key", nullable=False)
    op.create_foreign_key(
        f"{table_name}_organism_key_fkey",
        table_name,
        "organism",
        ["organism_key"],
        ["grouping_key"],
        ondelete="CASCADE" if table_name != "submission_attempt" else "RESTRICT",
    )
