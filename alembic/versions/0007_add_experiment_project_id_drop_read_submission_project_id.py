"""Add project_id to experiment and drop read_submission.project_id.

Revision ID: 0007_exp_proj_drop_readsub
Revises: 0006_sample_sub_project_id
Create Date: 2026-04-15 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0007_exp_proj_drop_readsub"
down_revision = "0006_sample_sub_project_id"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Add experiment.project_id (nullable initially for backfill)
    op.add_column(
        "experiment",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_foreign_key(
        "fk_experiment_project_id",
        "experiment",
        "project",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Backfill from experiment_submission.project_id where present.
    # Choose a deterministic candidate: the most recently updated submission row for each experiment.
    op.execute(
        """
        UPDATE experiment e
        SET project_id = es.project_id
        FROM (
            SELECT DISTINCT ON (experiment_id)
                experiment_id,
                project_id
            FROM experiment_submission
            WHERE project_id IS NOT NULL
            ORDER BY experiment_id, updated_at DESC, created_at DESC, id DESC
        ) es
        WHERE e.id = es.experiment_id
          AND e.project_id IS NULL
        """
    )

    # Ensure we didn't miss any experiments. If we did, this indicates inconsistent data.
    missing = (
        op.get_bind()
        .execute(sa.text("SELECT COUNT(*) FROM experiment WHERE project_id IS NULL"))
        .scalar()
    )
    if missing and int(missing) > 0:
        raise RuntimeError(
            f"Cannot apply migration: {missing} experiment rows have NULL project_id after backfill"
        )

    op.alter_column("experiment", "project_id", nullable=False)
    op.create_index("idx_experiment_project_id", "experiment", ["project_id"], unique=False)

    # 2) Drop read_submission.project_id (derivable via read_submission.experiment_id -> experiment.project_id)
    # Drop FK constraint + column using IF EXISTS (constraint name may vary by environment)
    op.execute(
        "ALTER TABLE read_submission DROP CONSTRAINT IF EXISTS read_submission_project_id_fkey"
    )
    op.execute(
        "ALTER TABLE read_submission DROP CONSTRAINT IF EXISTS read_submission_project_id_fkey1"
    )
    op.execute("ALTER TABLE read_submission DROP COLUMN IF EXISTS project_id")


def downgrade():
    # Re-add read_submission.project_id
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
        ondelete=None,
    )

    # Drop experiment.project_id
    op.drop_index("idx_experiment_project_id", table_name="experiment")
    op.drop_constraint("fk_experiment_project_id", "experiment", type_="foreignkey")
    op.drop_column("experiment", "project_id")
