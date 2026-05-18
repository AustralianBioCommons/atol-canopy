"""Remove submission_xml from assembly_submission table.

Revision ID: 0014_add_ncbi_taxonomy_details
Revises: 0013_remove_assembly_sub_col
Create Date: 2026-05-13

We are adding in NCBI taxonomy details for organisms, sourced through external API lookup to NCBI's Datasets API v2.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0014_add_ncbi_taxonomy_details"
down_revision = "0013_remove_assembly_sub_col"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("organism", "common_name_source")
    op.alter_column("organism", "genus", new_column_name="bpa_genus")
    op.alter_column("organism", "species", new_column_name="bpa_species")
    op.alter_column("organism", "common_name", new_column_name="bpa_common_name")
    op.alter_column(
        "organism", "infraspecific_epithet", new_column_name="bpa_infraspecific_epithet"
    )
    op.alter_column("organism", "culture_or_strain_id", new_column_name="bpa_culture_or_strain_id")
    op.alter_column("organism", "authority", new_column_name="bpa_authority")
    op.alter_column("organism", "scientific_name", new_column_name="bpa_scientific_name")
    op.add_column("organism", sa.Column("scientific_name", sa.Text(), nullable=True))

    op.drop_column("organism", "tax_string")
    op.drop_column("organism", "ncbi_order")
    op.drop_column("organism", "ncbi_family")
    op.drop_column("organism", "busco_dataset_name")
    op.drop_column("organism", "taxonomy_lineage_json")

    # Add new columns for NCBI taxonomy details
    op.add_column("taxonomy_info", sa.Column("ncbi_taxon_id", sa.Integer(), nullable=True))
    op.add_column("taxonomy_info", sa.Column("ncbi_rank", sa.String(), nullable=True))
    op.add_column("taxonomy_info", sa.Column("ncbi_scientific_name", sa.String(), nullable=True))
    op.add_column("taxonomy_info", sa.Column("ncbi_authority", sa.String(), nullable=True))
    op.add_column("taxonomy_info", sa.Column("ncbi_common_name", sa.String(), nullable=True))
    op.add_column("taxonomy_info", sa.Column("ncbi_class", sa.String(), nullable=True))
    op.add_column("taxonomy_info", sa.Column("ncbi_order", sa.String(), nullable=True))
    op.add_column("taxonomy_info", sa.Column("ncbi_family", sa.String(), nullable=True))
    op.add_column("taxonomy_info", sa.Column("ncbi_lineage", sa.JSON(), nullable=True))
    op.add_column("taxonomy_info", sa.Column("ncbi_tax_string", sa.String(), nullable=True))
    op.add_column("taxonomy_info", sa.Column("ncbi_full_lineage", sa.String(), nullable=True))
    op.add_column(
        "taxonomy_info",
        sa.Column("ncbi_last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("taxonomy_info", sa.Column("mito_ref", sa.String(), nullable=True))
    op.add_column("taxonomy_info", sa.Column("busco_dataset_name", sa.String(), nullable=True))
    op.execute("UPDATE organism SET scientific_name = bpa_scientific_name")
    op.execute(
        """
        UPDATE organism
        SET scientific_name = taxonomy_info.ncbi_scientific_name
        FROM taxonomy_info
        WHERE taxonomy_info.taxon_id = organism.taxon_id
          AND taxonomy_info.ncbi_scientific_name IS NOT NULL
        """
    )


def downgrade() -> None:
    # Drop columns added by the upgrade, in reverse order
    op.drop_column("taxonomy_info", "busco_dataset_name")
    op.drop_column("taxonomy_info", "mito_ref")
    op.drop_column("taxonomy_info", "ncbi_full_lineage")
    op.drop_column("taxonomy_info", "ncbi_tax_string")
    op.drop_column("taxonomy_info", "ncbi_lineage")
    op.drop_column("taxonomy_info", "ncbi_last_synced_at")
    op.drop_column("taxonomy_info", "ncbi_family")
    op.drop_column("taxonomy_info", "ncbi_order")
    op.drop_column("taxonomy_info", "ncbi_class")
    op.drop_column("taxonomy_info", "ncbi_common_name")
    op.drop_column("taxonomy_info", "ncbi_authority")
    op.drop_column("taxonomy_info", "ncbi_scientific_name")
    op.drop_column("taxonomy_info", "ncbi_rank")
    op.drop_column("taxonomy_info", "ncbi_taxon_id")

    # Restore columns that were dropped by the upgrade
    op.add_column(
        "organism",
        sa.Column("taxonomy_lineage_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("organism", sa.Column("busco_dataset_name", sa.Text(), nullable=True))
    op.add_column("organism", sa.Column("ncbi_family", sa.Text(), nullable=True))
    op.add_column("organism", sa.Column("ncbi_order", sa.Text(), nullable=True))
    op.add_column("organism", sa.Column("tax_string", sa.Text(), nullable=True))
    op.drop_column("organism", "scientific_name")

    # Rename BPA columns back to their original names
    op.alter_column("organism", "bpa_scientific_name", new_column_name="scientific_name")
    op.alter_column("organism", "bpa_authority", new_column_name="authority")
    op.alter_column(
        "organism",
        "bpa_culture_or_strain_id",
        new_column_name="culture_or_strain_id",
    )
    op.alter_column(
        "organism",
        "bpa_infraspecific_epithet",
        new_column_name="infraspecific_epithet",
    )
    op.alter_column("organism", "bpa_common_name", new_column_name="common_name")
    op.alter_column("organism", "bpa_species", new_column_name="species")
    op.alter_column("organism", "bpa_genus", new_column_name="genus")

    # Restore dropped BPA source column
    op.add_column("organism", sa.Column("common_name_source", sa.Text(), nullable=True))
