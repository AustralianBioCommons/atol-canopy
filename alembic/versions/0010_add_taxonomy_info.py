"""Add taxonomy_info table and migrate augustus_dataset_name off organism.

Revision ID: 0010_add_taxonomy_info
Revises: 0009_use_taxon_id_as_organism_pk
Create Date: 2026-05-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_add_taxonomy_info"
down_revision = "0009_use_taxon_id_as_organism_pk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create taxonomy_info table with PK = FK to organism.taxon_id
    op.create_table(
        "taxonomy_info",
        sa.Column("taxon_id", sa.Integer(), nullable=False),
        sa.Column("busco_odb10_dataset_name", sa.Text(), nullable=True),
        sa.Column("busco_odb12_dataset_name", sa.Text(), nullable=True),
        sa.Column("find_plastid", sa.Boolean(), nullable=True),
        sa.Column("hic_motif", sa.Text(), nullable=True),
        sa.Column("mitochondrial_genetic_code_id", sa.Integer(), nullable=True),
        sa.Column("mitohifi_reference_species", sa.Text(), nullable=True),
        sa.Column("oatk_hmm_name", sa.Text(), nullable=True),
        sa.Column("defined_class", sa.Text(), nullable=True),
        sa.Column("augustus_dataset_name", sa.Text(), nullable=True),
        sa.Column("genetic_code_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("taxon_id"),
        sa.ForeignKeyConstraint(
            ["taxon_id"], ["organism.taxon_id"], ondelete="CASCADE"
        ),
    )

    # 2. Migrate existing augustus_dataset_name values from organism into taxonomy_info
    op.execute("""
        INSERT INTO taxonomy_info (taxon_id, augustus_dataset_name)
        SELECT taxon_id, augustus_dataset_name
        FROM organism
        WHERE augustus_dataset_name IS NOT NULL
    """)

    # 3. Drop augustus_dataset_name from organism
    op.drop_column("organism", "augustus_dataset_name")


def downgrade() -> None:
    # 1. Restore the column on organism
    op.add_column("organism", sa.Column("augustus_dataset_name", sa.Text(), nullable=True))

    # 2. Copy data back from taxonomy_info
    op.execute("""
        UPDATE organism o
        SET augustus_dataset_name = ti.augustus_dataset_name
        FROM taxonomy_info ti
        WHERE o.taxon_id = ti.taxon_id
    """)

    # 3. Drop the taxonomy_info table
    op.drop_table("taxonomy_info")
