"""Add base_url column to experiment table.

Revision ID: 0008_add_base_url_to_experiment
Revises: 0007_add_qc_read_tables
Create Date: 2026-04-30 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_add_base_url_to_experiment"
down_revision = "0007_add_qc_read_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("experiment", sa.Column("base_url", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("experiment", "base_url")
