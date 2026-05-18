"""Remove submission_xml from assembly_submission table.

Revision ID: 0013_remove_assembly_sub_col
Revises: 0012_assembly_manifest_columns
Create Date: 2026-05-11

The submission_xml column is no longer used. Assembly submissions now use
manifest_json for storing submission data instead of XML format.
"""

import sqlalchemy as sa

from alembic import op

revision = "0013_remove_assembly_sub_col"
down_revision = "0012_assembly_manifest_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("assembly_submission", "submission_xml")


def downgrade() -> None:
    op.add_column(
        "assembly_submission",
        sa.Column("submission_xml", sa.Text(), nullable=True),
    )
