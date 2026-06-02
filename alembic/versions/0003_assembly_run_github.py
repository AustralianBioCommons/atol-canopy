"""Repurpose assembly_run as pipeline invocation (github_repo + git_commit); link stage runs to it.

Revision ID: 0003_assembly_run_github
Revises: 0002_update_taxon_cols
Create Date: 2026-05-28

Changes:
- Drop the legacy assembly_run table (version-reservation model, unused)
- Create new assembly_run table: (assembly_id, github_repo, git_commit)
  unique on (assembly_id, github_repo, git_commit)
- Alter assembly_stage_run:
    - Drop attempt column
    - Drop assembly_id FK column
    - Add assembly_run_id FK → assembly_run.id
    - Replace unique constraint uq_stage_run_assembly_stage_attempt
      with uq_stage_run_assembly_run_stage (assembly_run_id, stage_name)
    - Replace index ix_assembly_stage_run_assembly_id
      with ix_assembly_stage_run_assembly_run_id
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0003_assembly_run_github"
down_revision = "0002_update_taxon_cols"
branch_labels = None
depends_on = None

LEGACY_STAGE_RUN_REPO = "__legacy_stage_runs__"
LEGACY_STAGE_RUN_COMMIT = "pre-0003-migration"


def upgrade() -> None:
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
    # Drop old unique constraint and index
    op.drop_constraint("uq_stage_run_assembly_stage_attempt", "assembly_stage_run", type_="unique")
    op.drop_index("ix_assembly_stage_run_assembly_id", table_name="assembly_stage_run")

    # Add assembly_run_id as nullable first so existing rows can be backfilled.
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

    # Drop old columns once the replacement FK is populated.
    op.drop_column("assembly_stage_run", "attempt")
    op.drop_column("assembly_stage_run", "assembly_id")

    # New unique constraint and index
    op.create_unique_constraint(
        "uq_stage_run_assembly_run_stage",
        "assembly_stage_run",
        ["assembly_run_id", "stage_name"],
    )
    op.create_index(
        "ix_assembly_stage_run_assembly_run_id", "assembly_stage_run", ["assembly_run_id"]
    )


def downgrade() -> None:
    # ── Reverse assembly_stage_run changes ────────────────────────────────────
    op.drop_constraint("uq_stage_run_assembly_run_stage", "assembly_stage_run", type_="unique")
    op.drop_index("ix_assembly_stage_run_assembly_run_id", table_name="assembly_stage_run")
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
