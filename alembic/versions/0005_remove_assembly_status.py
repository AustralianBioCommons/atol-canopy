"""Remove assembly status and simplify qc_read_file.

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

    op.drop_constraint("ck_qc_read_file_md5", "qc_read_file", type_="check")
    op.drop_constraint("ck_qc_read_file_sha256", "qc_read_file", type_="check")

    op.alter_column("qc_read_file", "path_to_file", new_column_name="file_name")
    op.alter_column("qc_read_file", "md5_checksum", new_column_name="md5", nullable=False)
    op.alter_column("qc_read_file", "sha256_checksum", new_column_name="sha256", nullable=False)

    op.drop_column("qc_read_file", "storage_backend")
    op.drop_column("qc_read_file", "storage_profile")
    op.drop_column("qc_read_file", "bucket_name")

    op.create_check_constraint("ck_qc_read_file_md5", "qc_read_file", "md5 ~ '^[a-f0-9]{32}$'")
    op.create_check_constraint(
        "ck_qc_read_file_sha256", "qc_read_file", "sha256 ~ '^[a-f0-9]{64}$'"
    )


def downgrade() -> None:
    op.drop_constraint("ck_qc_read_file_md5", "qc_read_file", type_="check")
    op.drop_constraint("ck_qc_read_file_sha256", "qc_read_file", type_="check")

    op.add_column("qc_read_file", sa.Column("storage_backend", sa.Text(), nullable=True))
    op.add_column("qc_read_file", sa.Column("storage_profile", sa.Text(), nullable=True))
    op.add_column("qc_read_file", sa.Column("bucket_name", sa.Text(), nullable=True))

    op.alter_column("qc_read_file", "file_name", new_column_name="path_to_file")
    op.alter_column("qc_read_file", "md5", new_column_name="md5_checksum", nullable=False)
    op.alter_column("qc_read_file", "sha256", new_column_name="sha256_checksum", nullable=False)

    op.create_check_constraint(
        "ck_qc_read_file_md5", "qc_read_file", "md5_checksum ~ '^[a-f0-9]{32}$'"
    )
    op.create_check_constraint(
        "ck_qc_read_file_sha256", "qc_read_file", "sha256_checksum ~ '^[a-f0-9]{64}$'"
    )

    op.add_column(
        "assembly", sa.Column("status", sa.Text(), nullable=True, server_default="requested")
    )
    op.execute(sa.text("UPDATE assembly SET status = 'requested' WHERE status IS NULL"))
    op.alter_column("assembly", "status", nullable=False, server_default="requested")
    op.create_check_constraint(
        "ck_assembly_status",
        "assembly",
        "status IN ('requested', 'running', 'curating', 'completed', 'failed', 'cancelled')",
    )
