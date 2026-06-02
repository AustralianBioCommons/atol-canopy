"""Re-anchor qc_read on read_id and relax QC file reporting fields.

Revision ID: 0004_qc_reads_per_read_set
Revises: 0003_assembly_run_github
Create Date: 2026-06-02
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_qc_reads_per_read_set"
down_revision = "0003_assembly_run_github"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("qc_read", sa.Column("read_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_qc_read_read_id",
        "qc_read",
        "read",
        ["read_id"],
        ["id"],
        ondelete="CASCADE",
    )

    connection = op.get_bind()
    ambiguous_rows = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM qc_read q
            LEFT JOIN (
                SELECT experiment_id, COUNT(*) AS read_count, MIN(id) AS read_id
                FROM read
                GROUP BY experiment_id
            ) r ON r.experiment_id = q.experiment_id
            WHERE COALESCE(r.read_count, 0) <> 1
            """
        )
    ).scalar_one()
    if ambiguous_rows:
        raise RuntimeError(
            "Cannot migrate qc_read rows automatically: each existing qc_read must map to exactly one "
            "read via experiment_id. Resolve existing qc_read data before applying this migration."
        )

    connection.execute(
        sa.text(
            """
            UPDATE qc_read q
            SET read_id = r.read_id
            FROM (
                SELECT experiment_id, MIN(id) AS read_id
                FROM read
                GROUP BY experiment_id
            ) r
            WHERE r.experiment_id = q.experiment_id
            """
        )
    )

    op.alter_column("qc_read", "read_id", nullable=False)
    op.drop_index("idx_qc_read_experiment_id", table_name="qc_read")
    op.create_index("idx_qc_read_read_id", "qc_read", ["read_id"])
    op.drop_column("qc_read", "experiment_id")

    op.drop_constraint("ck_qc_read_file_type", "qc_read_file", type_="check")
    op.create_check_constraint(
        "ck_qc_read_file_type",
        "qc_read_file",
        "file_type IN ('cram', 'fastq', 'fastq_r1', 'fastq_r2')",
    )
    op.alter_column("qc_read_file", "storage_backend", nullable=True)
    op.alter_column("qc_read_file", "storage_profile", nullable=True)
    op.alter_column("qc_read_file", "bucket_name", nullable=True)

    op.drop_index("idx_qc_read_submission_experiment_id", table_name="qc_read_submission")
    op.drop_column("qc_read_submission", "experiment_id")


def downgrade() -> None:
    op.add_column(
        "qc_read_submission",
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_qc_read_submission_experiment_id",
        "qc_read_submission",
        "experiment",
        ["experiment_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_qc_read_submission_experiment_id",
        "qc_read_submission",
        ["experiment_id"],
    )

    op.alter_column("qc_read_file", "bucket_name", nullable=False)
    op.alter_column("qc_read_file", "storage_profile", nullable=False)
    op.alter_column("qc_read_file", "storage_backend", nullable=False)
    op.drop_constraint("ck_qc_read_file_type", "qc_read_file", type_="check")
    op.create_check_constraint(
        "ck_qc_read_file_type",
        "qc_read_file",
        "file_type IN ('cram', 'fastq_r1', 'fastq_r2')",
    )

    op.add_column(
        "qc_read",
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_qc_read_experiment_id",
        "qc_read",
        "experiment",
        ["experiment_id"],
        ["id"],
        ondelete="CASCADE",
    )

    connection = op.get_bind()
    unresolved_rows = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM qc_read q
            JOIN read r ON r.id = q.read_id
            WHERE r.experiment_id IS NULL
            """
        )
    ).scalar_one()
    if unresolved_rows:
        raise RuntimeError(
            "Cannot downgrade qc_read rows automatically because some linked reads have no experiment_id."
        )

    connection.execute(
        sa.text(
            """
            UPDATE qc_read q
            SET experiment_id = r.experiment_id
            FROM read r
            WHERE r.id = q.read_id
            """
        )
    )

    op.alter_column("qc_read", "experiment_id", nullable=False)
    op.drop_index("idx_qc_read_read_id", table_name="qc_read")
    op.create_index("idx_qc_read_experiment_id", "qc_read", ["experiment_id"])
    op.drop_constraint("fk_qc_read_read_id", "qc_read", type_="foreignkey")
    op.drop_column("qc_read", "read_id")
