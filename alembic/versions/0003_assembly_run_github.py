"""Refactor assembly reporting schema around pipeline invocations and stage results.

Revision ID: 0003_assembly_run_github
Revises: 0002_update_taxon_cols
Create Date: 2026-05-28

This squashes the branch-local reporting migrations into one revision:
- repurpose `assembly_run` as a pipeline invocation keyed by repo + commit
- remove `assembly.status`
- link `assembly_stage_run` to `assembly_run`
- remove stage-run `status`, rename `stats` -> `data`
- reshape stage-run files to `endpoint`, `location_root`, `location_path`, `sha256sum`
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0003_assembly_run_github"
down_revision = "0002_update_taxon_cols"
branch_labels = None
depends_on = None

LEGACY_STAGE_RUN_REPO = "__legacy_stage_runs__"
LEGACY_STAGE_RUN_COMMIT = "pre-0003-migration"


def upgrade() -> None:
    op.drop_constraint("ck_assembly_status", "assembly", type_="check", if_exists=True)
    op.drop_column("assembly", "status")

    # ── 1. Drop legacy assembly_run table ────────────────────────────────────
    op.drop_table("assembly_run")

    # ── 2. Create new assembly_run table ─────────────────────────────────────
    op.create_table(
        "assembly_run",
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
        sa.Column("github_repo", sa.Text(), nullable=False),
        sa.Column("git_commit", sa.Text(), nullable=False),
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
        sa.UniqueConstraint(
            "assembly_id",
            "github_repo",
            "git_commit",
            name="uq_assembly_run_assembly_repo_commit",
        ),
    )
    op.create_index("ix_assembly_run_assembly_id", "assembly_run", ["assembly_id"])

    # ── 3. Alter assembly_stage_run ───────────────────────────────────────────
    op.drop_constraint("uq_stage_run_assembly_stage_attempt", "assembly_stage_run", type_="unique")
    op.drop_index("ix_assembly_stage_run_assembly_id", table_name="assembly_stage_run")

    op.add_column(
        "assembly_stage_run",
        sa.Column(
            "assembly_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assembly_run.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # Create one synthetic assembly_run per assembly that already has stage-run rows.
    op.execute(
        sa.text(
            """
            INSERT INTO assembly_run (assembly_id, github_repo, git_commit)
            SELECT DISTINCT assembly_id, :github_repo, :git_commit
            FROM assembly_stage_run
            """
        ).bindparams(
            github_repo=LEGACY_STAGE_RUN_REPO,
            git_commit=LEGACY_STAGE_RUN_COMMIT,
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE assembly_stage_run AS stage_run
            SET assembly_run_id = assembly_run.id
            FROM assembly_run
            WHERE stage_run.assembly_id = assembly_run.assembly_id
              AND assembly_run.github_repo = :github_repo
              AND assembly_run.git_commit = :git_commit
            """
        ).bindparams(
            github_repo=LEGACY_STAGE_RUN_REPO,
            git_commit=LEGACY_STAGE_RUN_COMMIT,
        )
    )
    op.alter_column("assembly_stage_run", "assembly_run_id", nullable=False)

    op.drop_column("assembly_stage_run", "attempt")
    op.drop_column("assembly_stage_run", "assembly_id")
    op.drop_constraint(
        "ck_assembly_stage_run_status",
        "assembly_stage_run",
        type_="check",
        if_exists=True,
    )
    op.drop_column("assembly_stage_run", "status")
    op.alter_column("assembly_stage_run", "stats", new_column_name="data", nullable=False)

    op.create_unique_constraint(
        "uq_stage_run_assembly_run_stage",
        "assembly_stage_run",
        ["assembly_run_id", "stage_name"],
    )
    op.create_index(
        "ix_assembly_stage_run_assembly_run_id", "assembly_stage_run", ["assembly_run_id"]
    )

    # ── 4. Reshape assembly_stage_run_file ───────────────────────────────────
    op.add_column("assembly_stage_run_file", sa.Column("endpoint", sa.Text(), nullable=True))
    op.add_column("assembly_stage_run_file", sa.Column("location_root", sa.Text(), nullable=True))
    op.add_column("assembly_stage_run_file", sa.Column("location_path", sa.Text(), nullable=True))
    op.add_column(
        "assembly_stage_run_file",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE assembly_stage_run_file
            SET
                endpoint = NULLIF(storage_details->>'endpoint', ''),
                location_root = split_part(
                    regexp_replace(storage_uri, '^[a-zA-Z0-9+.-]+://', ''),
                    '/',
                    1
                ),
                location_path = regexp_replace(
                    regexp_replace(storage_uri, '^[a-zA-Z0-9+.-]+://', ''),
                    '^[^/]+/?',
                    ''
                ),
                updated_at = created_at
            """
        )
    )
    op.alter_column("assembly_stage_run_file", "location_root", nullable=False)
    op.alter_column("assembly_stage_run_file", "location_path", nullable=False)
    op.drop_column("assembly_stage_run_file", "storage_uri")
    op.drop_column("assembly_stage_run_file", "storage_details")


def downgrade() -> None:
    # ── Reverse assembly_stage_run_file changes ──────────────────────────────
    op.add_column(
        "assembly_stage_run_file",
        sa.Column("storage_details", JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "assembly_stage_run_file",
        sa.Column("storage_uri", sa.Text(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE assembly_stage_run_file
            SET
                storage_uri = CASE
                    WHEN location_root = '' THEN location_path
                    WHEN location_path = '' THEN storage_type || '://' || location_root
                    ELSE storage_type || '://' || location_root || '/' || location_path
                END,
                storage_details = CASE
                    WHEN endpoint IS NULL THEN '{}'::jsonb
                    ELSE jsonb_build_object('endpoint', endpoint)
                END
            """
        )
    )
    op.alter_column("assembly_stage_run_file", "storage_uri", nullable=False)
    op.alter_column(
        "assembly_stage_run_file",
        "storage_details",
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        existing_type=JSONB(),
    )
    op.drop_column("assembly_stage_run_file", "updated_at")
    op.drop_column("assembly_stage_run_file", "location_path")
    op.drop_column("assembly_stage_run_file", "location_root")
    op.drop_column("assembly_stage_run_file", "endpoint")

    # ── Reverse assembly_stage_run changes ────────────────────────────────────
    op.drop_constraint("uq_stage_run_assembly_run_stage", "assembly_stage_run", type_="unique")
    op.drop_index("ix_assembly_stage_run_assembly_run_id", table_name="assembly_stage_run")
    op.alter_column("assembly_stage_run", "data", new_column_name="stats", nullable=False)
    op.add_column("assembly_stage_run", sa.Column("status", sa.Text(), nullable=True))
    op.execute(sa.text("UPDATE assembly_stage_run SET status = 'succeeded' WHERE status IS NULL"))
    op.alter_column("assembly_stage_run", "status", nullable=False)
    op.create_check_constraint(
        "ck_assembly_stage_run_status",
        "assembly_stage_run",
        "status IN ('running', 'succeeded', 'failed', 'cancelled')",
    )
    op.add_column(
        "assembly_stage_run",
        sa.Column(
            "assembly_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assembly.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE assembly_stage_run AS stage_run
            SET assembly_id = assembly_run.assembly_id
            FROM assembly_run
            WHERE stage_run.assembly_run_id = assembly_run.id
            """
        )
    )
    op.alter_column("assembly_stage_run", "assembly_id", nullable=False)
    op.add_column(
        "assembly_stage_run",
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
    )
    op.drop_column("assembly_stage_run", "assembly_run_id")
    op.create_unique_constraint(
        "uq_stage_run_assembly_stage_attempt",
        "assembly_stage_run",
        ["assembly_id", "stage_name", "attempt"],
    )
    op.create_index("ix_assembly_stage_run_assembly_id", "assembly_stage_run", ["assembly_id"])

    # ── Drop new assembly_run, restore legacy one ─────────────────────────────
    op.drop_table("assembly_run")

    op.create_table(
        "assembly_run",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("taxon_id", sa.Integer(), sa.ForeignKey("organism.taxon_id"), nullable=False),
        sa.Column("sample_id", UUID(as_uuid=True), sa.ForeignKey("sample.id"), nullable=False),
        sa.Column(
            "data_types",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("tol_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="reserved"),
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
