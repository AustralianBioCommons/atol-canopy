"""Assembly-first manifest flow: nullable fields, status, and stage reporting tables.

Revision ID: 0011_assembly_first_and_stages
Revises: 0010_add_taxonomy_info
Create Date: 2026-05-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0011_assembly_first_and_stages"
down_revision = "0010_add_taxonomy_info"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Make late-known assembly fields nullable ──────────────────────────
    op.alter_column("assembly", "assembly_name", existing_type=sa.Text(), nullable=True)
    op.alter_column("assembly", "coverage", existing_type=sa.Float(), nullable=True)
    op.alter_column("assembly", "program", existing_type=sa.Text(), nullable=True)

    # ── 2. Add lifecycle status to assembly ───────────────────────────────────
    op.add_column(
        "assembly",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="requested",
        ),
    )
    op.create_check_constraint(
        "ck_assembly_status",
        "assembly",
        "status IN ('requested', 'running', 'curating', 'completed', 'failed', 'cancelled')",
    )

    # ── 3. assembly_stage catalog ─────────────────────────────────────────────
    op.create_table(
        "assembly_stage",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("category IN ('pipeline', 'manual')", name="ck_assembly_stage_category"),
    )

    op.execute(
        """
        INSERT INTO assembly_stage (name, category) VALUES
            ('genomeassembly', 'pipeline'),
            ('ascc', 'pipeline'),
            ('treeval', 'pipeline'),
            ('curation-pretext', 'pipeline'),
            ('manual-curation', 'manual')
        """
    )

    # ── 4. assembly_stage_run ─────────────────────────────────────────────────
    op.create_table(
        "assembly_stage_run",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "assembly_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assembly.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stage_name",
            sa.Text(),
            sa.ForeignKey("assembly_stage.name"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("external_run_id", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("stats", JSONB(), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'cancelled')",
            name="ck_assembly_stage_run_status",
        ),
        sa.UniqueConstraint("assembly_id", "stage_name", "attempt", name="uq_stage_run_assembly_stage_attempt"),
    )
    op.create_index("ix_assembly_stage_run_assembly_id", "assembly_stage_run", ["assembly_id"])

    # ── 5. assembly_stage_run_file ────────────────────────────────────────────
    op.create_table(
        "assembly_stage_run_file",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "assembly_stage_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assembly_stage_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_type", sa.Text(), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("storage_details", JSONB(), nullable=False, server_default="{}"),
        sa.Column("sha256sum", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_assembly_stage_run_file_run_id",
        "assembly_stage_run_file",
        ["assembly_stage_run_id"],
    )


def downgrade() -> None:
    op.drop_table("assembly_stage_run_file")
    op.drop_table("assembly_stage_run")
    op.drop_table("assembly_stage")

    op.drop_constraint("ck_assembly_status", "assembly", type_="check")
    op.drop_column("assembly", "status")

    op.alter_column("assembly", "program", existing_type=sa.Text(), nullable=False)
    op.alter_column("assembly", "coverage", existing_type=sa.Float(), nullable=False)
    op.alter_column("assembly", "assembly_name", existing_type=sa.Text(), nullable=False)
