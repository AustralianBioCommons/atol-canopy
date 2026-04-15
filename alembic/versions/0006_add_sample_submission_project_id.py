"""Add project_id to sample_submission for normalized accession lookups.

Revision ID: 0006_sample_sub_project_id
Revises: 0005_org_sci_name_nullable
Create Date: 2026-04-13 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_sample_sub_project_id"
down_revision = "0005_org_sci_name_nullable"
branch_labels = None
depends_on = None


def upgrade():
    # Add project_id column to sample_submission
    op.add_column(
        "sample_submission",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_sample_submission_project_id",
        "sample_submission",
        "project",
        ["project_id"],
        ["id"],
    )

    # Backfill project_id from organism's genomic_data project
    op.execute("""
        UPDATE sample_submission ss
        SET project_id = p.id
        FROM sample s
        JOIN project p ON p.organism_key = s.organism_key AND p.project_type = 'genomic_data'
        WHERE ss.sample_id = s.id
          AND ss.project_id IS NULL
    """)

    # Make project_id NOT NULL now that it's backfilled
    op.alter_column("sample_submission", "project_id", nullable=False)

    # Add index for performance
    op.create_index(
        "idx_sample_submission_project_id",
        "sample_submission",
        ["project_id"],
        unique=False,
    )


def downgrade():
    # Drop index
    op.drop_index("idx_sample_submission_project_id", table_name="sample_submission")

    # Drop foreign key constraint
    op.drop_constraint("fk_sample_submission_project_id", "sample_submission", type_="foreignkey")

    # Drop column
    op.drop_column("sample_submission", "project_id")
