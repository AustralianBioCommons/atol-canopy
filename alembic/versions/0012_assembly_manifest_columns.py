"""Add specimen sample IDs and manifest JSON to assembly.

Revision ID: 0012_assembly_manifest_columns
Revises: 0011_assembly_first_and_stages
Create Date: 2026-05-08

Adds three nullable columns to the assembly table:
- long_read_specimen_sample_id: the specimen sample used for long reads (PacBio / ONT)
- hic_specimen_sample_id: the specimen sample used for Hi-C reads (optional)
- manifest_json: persisted JSON manifest generated at intent time

All columns are nullable so existing rows are unaffected.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0012_assembly_manifest_columns"
down_revision = "0011_assembly_first_and_stages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assembly",
        sa.Column(
            "long_read_specimen_sample_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sample.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "assembly",
        sa.Column(
            "hic_specimen_sample_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sample.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "assembly",
        sa.Column("manifest_json", JSONB(), nullable=True),
    )
    op.create_index(
        "idx_assembly_intent_version_key",
        "assembly",
        ["taxon_id", "long_read_specimen_sample_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_assembly_intent_version_key", table_name="assembly")
    op.drop_column("assembly", "manifest_json")
    op.drop_column("assembly", "hic_specimen_sample_id")
    op.drop_column("assembly", "long_read_specimen_sample_id")
