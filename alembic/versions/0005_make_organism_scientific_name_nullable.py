"""Make organism.scientific_name nullable.

Revision ID: 0005_make_organism_scientific_name_nullable
Revises: 0004_add_assembly_run
Create Date: 2026-03-04 00:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_make_organism_scientific_name_nullable"
down_revision = "0004_add_assembly_run"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE organism ALTER COLUMN scientific_name DROP NOT NULL;")


def downgrade():
    op.execute("UPDATE organism SET scientific_name = grouping_key WHERE scientific_name IS NULL;")
    op.execute("ALTER TABLE organism ALTER COLUMN scientific_name SET NOT NULL;")
