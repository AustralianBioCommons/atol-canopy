"""Add hic_specimen_sample_ids JSONB column to assembly table.

Revision ID: 0003_add_hic_specimen_sample_ids
Revises: 0002_update_taxon_cols
Create Date: 2026-05-20
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0003_add_hic_specimen_sample_ids"
down_revision = "0002_update_taxon_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assembly", sa.Column("hic_specimen_sample_ids", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("assembly", "hic_specimen_sample_ids")
