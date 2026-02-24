"""Add tol_id to assembly.

Revision ID: 0003_add_tol_id_to_assembly
Revises: 0002_timestamptz_and_broker_indexes
Create Date: 2026-02-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_add_tol_id_to_assembly"
down_revision = "0002_timestamptz_and_broker_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("assembly", sa.Column("tol_id", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("assembly", "tol_id")
