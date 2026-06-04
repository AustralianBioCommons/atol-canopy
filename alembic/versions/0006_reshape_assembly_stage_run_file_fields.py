"""Reshape assembly stage run file storage fields.

Revision ID: 0006_reshape_assembly_stage_run_file_fields
Revises: 0005_remove_assembly_status
Create Date: 2026-06-04
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_reshape_assembly_stage_run_file_fields"
down_revision = "0005_remove_assembly_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assembly_stage_run_file", sa.Column("endpoint", sa.Text(), nullable=False))
    op.add_column(
        "assembly_stage_run_file",
        sa.Column("location_root", sa.Text(), nullable=False),
    )
    op.add_column(
        "assembly_stage_run_file",
        sa.Column("location_path", sa.Text(), nullable=False),
    )
    op.add_column(
        "assembly_stage_run_file",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.alter_column("assembly_stage_run_file", "sha256sum", nullable=False)

    op.drop_column("assembly_stage_run_file", "storage_uri")
    op.drop_column("assembly_stage_run_file", "storage_details")


def downgrade() -> None:
    op.add_column(
        "assembly_stage_run_file",
        sa.Column(
            "storage_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "assembly_stage_run_file",
        sa.Column("storage_uri", sa.Text(), nullable=True),
    )

    op.alter_column("assembly_stage_run_file", "storage_uri", nullable=False)

    op.drop_column("assembly_stage_run_file", "updated_at")
    op.drop_column("assembly_stage_run_file", "location_path")
    op.drop_column("assembly_stage_run_file", "location_root")
    op.drop_column("assembly_stage_run_file", "endpoint")
