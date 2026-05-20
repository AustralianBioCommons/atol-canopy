"""Remove outdated columns from taxonomy_info table.

Revision ID: 0002_update_taxon_cols
Revises: 0001_initial_schema
Create Date: 2026-05-11

Removing columns "defined_class" (redundant with "ncbi_class"), "mito_ref" (redundant with "mitohifi_reference_species"), and
"busco_dataset_name" (replaced by "busco_odb10_dataset_name" and "busco_odb12_dataset_name"). Also adding "hic_specimen_sample_ids"
column to assembly table, to replace "hic_specimen_sample_id".
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0002_update_taxon_cols"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("taxonomy_info", "defined_class")
    op.execute(
        sa.text(
            """
            UPDATE taxonomy_info
            SET mitohifi_reference_species = COALESCE(mitohifi_reference_species, mito_ref)
            WHERE mito_ref IS NOT NULL
            """
        )
    )
    op.drop_column("taxonomy_info", "mito_ref")
    op.drop_column("taxonomy_info", "busco_dataset_name")
    op.add_column("assembly", sa.Column("hic_specimen_sample_ids", JSONB, nullable=True))


def downgrade() -> None:
    op.add_column(
        "taxonomy_info",
        sa.Column("defined_class", sa.Text(), nullable=True),
    )
    op.add_column(
        "taxonomy_info",
        sa.Column("mito_ref", sa.Text(), nullable=True),
    )
    op.add_column(
        "taxonomy_info",
        sa.Column("busco_dataset_name", sa.Text(), nullable=True),
    )
    op.drop_column("assembly", "hic_specimen_sample_ids")
