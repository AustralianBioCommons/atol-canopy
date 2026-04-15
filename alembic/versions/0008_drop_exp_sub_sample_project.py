"""Drop redundant experiment_submission.sample_id and project_id.

Revision ID: 0008_drop_exp_sub_s_p
Revises: 0007_exp_proj_drop_readsub
Create Date: 2026-04-15 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_drop_exp_sub_s_p"
down_revision = "0007_exp_proj_drop_readsub"
branch_labels = None
depends_on = None


def upgrade():
    # Drop foreign keys if they exist (names can vary)
    op.execute(
        "ALTER TABLE experiment_submission DROP CONSTRAINT IF EXISTS experiment_submission_sample_id_fkey"
    )
    op.execute(
        "ALTER TABLE experiment_submission DROP CONSTRAINT IF EXISTS experiment_submission_project_id_fkey"
    )

    # Drop columns
    op.execute("ALTER TABLE experiment_submission DROP COLUMN IF EXISTS sample_id")
    op.execute("ALTER TABLE experiment_submission DROP COLUMN IF EXISTS project_id")


def downgrade():
    # Re-add columns (nullable during backfill)
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
        ondelete=None,
    )
    op.create_foreign_key(
        "experiment_submission_project_id_fkey",
        "experiment_submission",
        "project",
        ["project_id"],
        ["id"],
        ondelete=None,
    )

    # Backfill from experiment
    op.execute(
        """
        UPDATE experiment_submission es
        SET sample_id = e.sample_id,
            project_id = e.project_id
        FROM experiment e
        WHERE es.experiment_id = e.id
        """
    )

    op.alter_column("experiment_submission", "sample_id", nullable=False)
