"""Add qc_read source read file checksums and assembly association.

Revision ID: 0004_qc_reads_assembly_refs
Revises: 0003_assembly_run_github
Create Date: 2026-06-02
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_qc_reads_assembly_refs"
down_revision = "0003_assembly_run_github"
branch_labels = None
depends_on = None


def _drop_qc_read_file_type_checks() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                constraint_name text;
            BEGIN
                FOR constraint_name IN
                    SELECT c.conname
                    FROM pg_constraint AS c
                    JOIN pg_class AS t ON t.oid = c.conrelid
                    JOIN pg_namespace AS n ON n.oid = t.relnamespace
                    WHERE t.relname = 'qc_read_file'
                      AND n.nspname = current_schema()
                      AND c.contype = 'c'
                      AND pg_get_constraintdef(c.oid) LIKE '%file_type%'
                LOOP
                    EXECUTE format(
                        'ALTER TABLE %I DROP CONSTRAINT %I',
                        'qc_read_file',
                        constraint_name
                    );
                END LOOP;
            END $$;
            """
        )
    )


def upgrade() -> None:
    op.add_column(
        "qc_read",
        sa.Column("source_read_file_checksums", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.execute("UPDATE qc_read SET source_read_file_checksums = ARRAY[]::text[]")
    op.alter_column("qc_read", "source_read_file_checksums", nullable=False)

    op.create_table(
        "qc_read_assembly",
        sa.Column(
            "assembly_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assembly.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "qc_read_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("qc_read.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index("idx_qc_read_assembly_qc_read_id", "qc_read_assembly", ["qc_read_id"])

    _drop_qc_read_file_type_checks()
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
    op.execute(
        sa.text(
            """
            UPDATE qc_read_submission AS submission
            SET experiment_id = qc_read.experiment_id
            FROM qc_read
            WHERE submission.qc_read_id = qc_read.id
              AND submission.experiment_id IS NULL
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE qc_read_file
            SET
                storage_backend = COALESCE(storage_backend, 'legacy_unknown'),
                storage_profile = COALESCE(storage_profile, 'legacy_unknown'),
                bucket_name = COALESCE(bucket_name, 'legacy_unknown')
            WHERE storage_backend IS NULL
               OR storage_profile IS NULL
               OR bucket_name IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE qc_read_file
            SET file_type = 'fastq_r1'
            WHERE file_type = 'fastq'
            """
        )
    )

    op.alter_column("qc_read_file", "bucket_name", nullable=False)
    op.alter_column("qc_read_file", "storage_profile", nullable=False)
    op.alter_column("qc_read_file", "storage_backend", nullable=False)
    _drop_qc_read_file_type_checks()
    op.create_check_constraint(
        "ck_qc_read_file_type",
        "qc_read_file",
        "file_type IN ('cram', 'fastq_r1', 'fastq_r2')",
    )

    op.drop_index("idx_qc_read_assembly_qc_read_id", table_name="qc_read_assembly")
    op.drop_table("qc_read_assembly")

    op.drop_column("qc_read", "source_read_file_checksums", if_exists=True)
