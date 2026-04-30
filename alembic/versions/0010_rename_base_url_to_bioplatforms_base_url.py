"""Rename base_url to bioplatforms_base_url in experiment table.

Revision ID: 0010_rename_base_url
Revises: 0009_use_taxon_id_as_organism_pk
Create Date: 2026-04-30 22:46:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0010_rename_base_url"
down_revision = "0009_use_taxon_id_as_organism_pk"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("experiment", "base_url", new_column_name="bioplatforms_base_url")


def downgrade():
    op.alter_column("experiment", "bioplatforms_base_url", new_column_name="base_url")
