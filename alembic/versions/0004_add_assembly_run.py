"""Add assembly_run table.

Revision ID: 0004_add_assembly_run
Revises: 0003_add_tol_id_to_assembly
Create Date: 2026-02-24 00:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_add_assembly_run"
down_revision = "0003_add_tol_id_to_assembly"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS assembly_run (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            organism_key TEXT REFERENCES organism(grouping_key) NOT NULL,
            sample_id UUID REFERENCES sample(id) NOT NULL,
            data_types assembly_data_types NOT NULL,
            version INTEGER NOT NULL,
            tol_id TEXT,
            status TEXT NOT NULL DEFAULT 'reserved',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS assembly_run;")
