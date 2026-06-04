"""Remove assembly stage run status and rename stats to data.

Revision ID: 0007_update_stage_run_fields
Revises: 0006_reshape_assembly_sr_file
Create Date: 2026-06-05
"""

import sqlalchemy as sa

from alembic import op

revision = "0007_update_stage_run_fields"
down_revision = "0006_reshape_assembly_sr_file"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_assembly_stage_run_status",
        "assembly_stage_run",
        type_="check",
        if_exists=True,
    )
    op.drop_column("assembly_stage_run", "status")
    op.alter_column("assembly_stage_run", "stats", new_column_name="data", nullable=False)


def downgrade() -> None:
    op.alter_column("assembly_stage_run", "data", new_column_name="stats", nullable=False)
    op.add_column("assembly_stage_run", sa.Column("status", sa.Text(), nullable=True))
    op.execute(sa.text("UPDATE assembly_stage_run SET status = 'succeeded' WHERE status IS NULL"))
    op.alter_column("assembly_stage_run", "status", nullable=False)
    op.create_check_constraint(
        "ck_assembly_stage_run_status",
        "assembly_stage_run",
        "status IN ('running', 'succeeded', 'failed', 'cancelled')",
    )
