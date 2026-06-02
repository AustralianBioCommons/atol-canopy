"""Remove assembly status column.

Revision ID: 0005_remove_assembly_status
Revises: 0004_qc_reads_assembly_refs
Create Date: 2026-06-02
"""

import sqlalchemy as sa

from alembic import op

revision = "0005_remove_assembly_status"
down_revision = "0004_qc_reads_assembly_refs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_assembly_status", "assembly", type_="check")
    op.drop_column("assembly", "status")


def downgrade() -> None:
    op.add_column("assembly", sa.Column("status", sa.Text(), nullable=True, server_default="requested"))
    op.execute(sa.text("UPDATE assembly SET status = 'requested' WHERE status IS NULL"))
    op.alter_column("assembly", "status", nullable=False, server_default="requested")
    op.create_check_constraint(
        "ck_assembly_status",
        "assembly",
        "status IN ('requested', 'running', 'curating', 'completed', 'failed', 'cancelled')",
    )
