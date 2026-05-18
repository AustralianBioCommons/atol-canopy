"""Add qc_read, qc_read_file, qc_read_submission; drop read_submission.

Revision ID: 0007_add_qc_read_tables
Revises: 0006_consolidated_refactor
Create Date: 2026-04-29 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007_add_qc_read_tables"
down_revision = "0006_consolidated_refactor"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Extend the entity_type enum to include 'qc_read'.
    # ALTER TYPE … ADD VALUE must be committed before the new value can be used.
    # Since Alembic runs migrations in a transaction, we must manually commit,
    # add the enum value, then begin a new transaction.
    connection = op.get_bind()
    connection.execute(sa.text("COMMIT"))
    connection.execute(sa.text("ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'qc_read'"))
    connection.execute(sa.text("BEGIN"))

    # 2. Create qc_read table.
    op.create_table(
        "qc_read",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("base_count", sa.BigInteger, nullable=False),
        sa.Column("read_count", sa.BigInteger, nullable=False),
        sa.Column("qc_bases_removed", sa.BigInteger, nullable=False),
        sa.Column("qc_reads_removed", sa.BigInteger, nullable=False),
        sa.Column("mean_gc_content", sa.Float, nullable=False),
        sa.Column("n50_length", sa.BigInteger, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_qc_read_experiment_id", "qc_read", ["experiment_id"])

    # 3. Create qc_read_file table.
    op.create_table(
        "qc_read_file",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "qc_read_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("qc_read.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # 'cram', 'fastq_r1', or 'fastq_r2'
        sa.Column("file_type", sa.Text, nullable=False),
        sa.Column("storage_backend", sa.Text, nullable=False),
        sa.Column("storage_profile", sa.Text, nullable=False),
        sa.Column("bucket_name", sa.Text, nullable=False),
        sa.Column("path_to_file", sa.Text, nullable=False),
        sa.Column("md5_checksum", sa.Text, nullable=False),
        sa.Column("sha256_checksum", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "file_type IN ('cram', 'fastq_r1', 'fastq_r2')",
            name="ck_qc_read_file_type",
        ),
        sa.CheckConstraint(
            "md5_checksum ~ '^[a-f0-9]{32}$'",
            name="ck_qc_read_file_md5",
        ),
        sa.CheckConstraint(
            "sha256_checksum ~ '^[a-f0-9]{64}$'",
            name="ck_qc_read_file_sha256",
        ),
    )
    op.create_index("idx_qc_read_file_qc_read_id", "qc_read_file", ["qc_read_id"])

    # 4. Create qc_read_submission table (mirrors read_submission; FK to qc_read).
    op.create_table(
        "qc_read_submission",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "qc_read_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("qc_read.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiment.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "authority",
            postgresql.ENUM("ENA", "NCBI", "DDBJ", name="authority_type", create_type=False),
            nullable=False,
            server_default="ENA",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "ready",
                "submitting",
                "accepted",
                "rejected",
                "replaced",
                name="submission_status",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("prepared_payload", postgresql.JSONB, nullable=False),
        sa.Column("response_payload", postgresql.JSONB, nullable=True),
        sa.Column("accession", sa.Text, nullable=True),
        sa.Column(
            "entity_type_const",
            postgresql.ENUM(
                "organism",
                "sample",
                "experiment",
                "read",
                "assembly",
                "project",
                "qc_read",
                name="entity_type",
                create_type=False,
            ),
            nullable=False,
            server_default="qc_read",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finalised_attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lock_acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "entity_type_const = 'qc_read'",
            name="ck_qc_read_submission_entity_type",
        ),
        # Deferred FK to accession_registry, matching the read_submission pattern.
        sa.ForeignKeyConstraint(
            ["accession", "authority", "entity_type_const", "qc_read_id"],
            [
                "accession_registry.accession",
                "accession_registry.authority",
                "accession_registry.entity_type",
                "accession_registry.entity_id",
            ],
            name="fk_qc_read_submission_accession",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.create_index("idx_qc_read_submission_attempt", "qc_read_submission", ["attempt_id"])
    op.create_index(
        "idx_qc_read_submission_finalised_attempt",
        "qc_read_submission",
        ["finalised_attempt_id"],
    )
    op.create_index("idx_qc_read_submission_status", "qc_read_submission", ["status"])
    op.create_index(
        "idx_qc_read_submission_lock_expires_at", "qc_read_submission", ["lock_expires_at"]
    )
    op.create_index("idx_qc_read_submission_experiment_id", "qc_read_submission", ["experiment_id"])
    # Partial unique index: at most one accepted accession per (qc_read, authority).
    op.execute(
        """
        CREATE UNIQUE INDEX uq_qc_read_one_accepted
        ON qc_read_submission (qc_read_id, authority)
        WHERE status = 'accepted' AND accession IS NOT NULL
        """
    )

    # 5. Drop read_submission (no data migration required).
    op.execute("DROP TABLE IF EXISTS read_submission CASCADE")


def downgrade():
    # Re-create read_submission
    op.create_table(
        "read_submission",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "read_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("read.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "authority",
            postgresql.ENUM("ENA", "NCBI", "DDBJ", name="authority_type", create_type=False),
            nullable=False,
            server_default="ENA",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "ready",
                "submitting",
                "accepted",
                "rejected",
                "replaced",
                name="submission_status",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("prepared_payload", postgresql.JSONB, nullable=False),
        sa.Column("response_payload", postgresql.JSONB, nullable=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiment.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("accession", sa.Text, nullable=True),
        sa.Column("entity_type_const", sa.Text, nullable=False, server_default="read"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finalised_attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lock_acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Drop qc_read_submission (cascades indexes)
    op.drop_table("qc_read_submission")
    # Drop qc_read_file and qc_read (cascade)
    op.drop_table("qc_read_file")
    op.drop_table("qc_read")
    # Note: cannot remove enum values in PostgreSQL; qc_read stays in entity_type enum.
