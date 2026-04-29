"""Consolidated submission schema refactor.

This migration consolidates the following changes:
- Add project_id to sample_submission (NOT NULL, FK to project)
- Add project_id to experiment (NOT NULL, FK to project)
- Drop project_id from read_submission (derivable via experiment)
- Drop sample_id and project_id from experiment_submission (derivable via experiment)

Note: No backfill logic included - database will be repopulated after merge.

Revision ID: 0006_consolidated_refactor
Revises: 0005_org_sci_name_nullable
Create Date: 2026-04-22 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_consolidated_refactor"
down_revision = "0005_org_sci_name_nullable"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Add sample_submission.project_id (NOT NULL, FK to project)
    op.add_column(
        "sample_submission",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_sample_submission_project_id",
        "sample_submission",
        "project",
        ["project_id"],
        ["id"],
    )
    op.create_index(
        "idx_sample_submission_project_id",
        "sample_submission",
        ["project_id"],
        unique=False,
    )

    # 2) Add experiment.project_id (NOT NULL, FK to project with CASCADE)
    op.add_column(
        "experiment",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_experiment_project_id",
        "experiment",
        "project",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_experiment_project_id",
        "experiment",
        ["project_id"],
        unique=False,
    )

    # 3) Drop read_submission.project_id (derivable via experiment)
    op.execute(
        "ALTER TABLE read_submission DROP CONSTRAINT IF EXISTS read_submission_project_id_fkey"
    )
    op.execute(
        "ALTER TABLE read_submission DROP CONSTRAINT IF EXISTS read_submission_project_id_fkey1"
    )
    op.execute("ALTER TABLE read_submission DROP COLUMN IF EXISTS project_id")

    # 4) Drop experiment_submission.sample_id and project_id (derivable via experiment)
    op.execute(
        "ALTER TABLE experiment_submission DROP CONSTRAINT IF EXISTS experiment_submission_sample_id_fkey"
    )
    op.execute(
        "ALTER TABLE experiment_submission DROP CONSTRAINT IF EXISTS experiment_submission_project_id_fkey"
    )
    op.execute("ALTER TABLE experiment_submission DROP COLUMN IF EXISTS sample_id")
    op.execute("ALTER TABLE experiment_submission DROP COLUMN IF EXISTS project_id")


def downgrade():
    # Reverse order of upgrade

    # 4) Re-add experiment_submission.sample_id and project_id
    op.add_column(
        "experiment_submission",
        sa.Column("sample_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "experiment_submission",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "experiment_submission_sample_id_fkey",
        "experiment_submission",
        "sample",
        ["sample_id"],
        ["id"],
    )
    op.create_foreign_key(
        "experiment_submission_project_id_fkey",
        "experiment_submission",
        "project",
        ["project_id"],
        ["id"],
    )

    # 3) Re-add read_submission.project_id
    op.add_column(
        "read_submission",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "read_submission_project_id_fkey",
        "read_submission",
        "project",
        ["project_id"],
        ["id"],
    )

    # 2) Drop experiment.project_id
    op.drop_index("idx_experiment_project_id", table_name="experiment")
    op.drop_constraint("fk_experiment_project_id", "experiment", type_="foreignkey")
    op.drop_column("experiment", "project_id")

    # 1) Drop sample_submission.project_id
    op.drop_index("idx_sample_submission_project_id", table_name="sample_submission")
    op.drop_constraint("fk_sample_submission_project_id", "sample_submission", type_="foreignkey")
    op.drop_column("sample_submission", "project_id")
