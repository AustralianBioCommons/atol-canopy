"""Add durable ToLID request state.

Revision ID: 0005_add_tolid_requests
Revises: 0004_qc_reads_assembly_refs
Create Date: 2026-06-16
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005_add_tolid_requests"
down_revision = "0004_qc_reads_assembly_refs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tolid_status = postgresql.ENUM(
        "not_requested",
        "pending",
        "assigned",
        "failed",
        name="tolid_request_status",
    )
    tolid_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tolid_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "sample_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sample.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tolid_external_id", sa.Text(), nullable=False),
        sa.Column(
            "taxon_id",
            sa.Integer(),
            sa.ForeignKey("organism.taxon_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scientific_name", sa.Text(), nullable=True),
        sa.Column("tolid", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "not_requested",
                "pending",
                "assigned",
                "failed",
                name="tolid_request_status",
                create_type=False,
            ),
            nullable=False,
            server_default="not_requested",
        ),
        sa.Column("last_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("uq_tolid_request_sample_id", "tolid_request", ["sample_id"], unique=True)
    op.create_index("idx_tolid_request_status", "tolid_request", ["status"])
    op.create_index(
        "idx_tolid_request_status_last_requested_at",
        "tolid_request",
        ["status", "last_requested_at"],
    )
    op.create_index("idx_tolid_request_request_id", "tolid_request", ["request_id"])


def downgrade() -> None:
    op.drop_index("idx_tolid_request_request_id", table_name="tolid_request")
    op.drop_index("idx_tolid_request_status_last_requested_at", table_name="tolid_request")
    op.drop_index("idx_tolid_request_status", table_name="tolid_request")
    op.drop_index("uq_tolid_request_sample_id", table_name="tolid_request")
    op.drop_table("tolid_request")

    tolid_status = postgresql.ENUM(
        "not_requested",
        "pending",
        "assigned",
        "failed",
        name="tolid_request_status",
    )
    tolid_status.drop(op.get_bind(), checkfirst=True)
