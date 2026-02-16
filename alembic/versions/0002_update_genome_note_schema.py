"""Update genome_note schema with versioning and direct assembly link.

Revision ID: 0002_update_genome_note_schema
Revises: 0001_initial_schema
Create Date: 2026-02-09

Changes:
- Drop genome_note_assembly junction table
- Remove genome_note_assembly_id from genome_note
- Add assembly_id (direct FK to assembly)
- Add version (integer, auto-increment per organism)
- Add note_url (text, required)
- Add published_at (timestamp, nullable)
- Add unique constraint on (organism_key, version)
- Add indexes for efficient lookups
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002_update_genome_note_schema"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the genome_note_assembly junction table
    op.drop_table("genome_note_assembly")

    # Remove the old genome_note_assembly_id column
    op.drop_column("genome_note", "genome_note_assembly_id")

    # Add new columns to genome_note table
    op.add_column(
        "genome_note",
        sa.Column(
            "assembly_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,  # Temporarily nullable for migration
        ),
    )
    op.add_column(
        "genome_note",
        sa.Column("version", sa.Integer(), nullable=True),  # Temporarily nullable
    )
    op.add_column(
        "genome_note",
        sa.Column("note_url", sa.Text(), nullable=True),  # Temporarily nullable
    )
    op.add_column(
        "genome_note",
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )

    # Populate version numbers for existing records (if any)
    # This assigns version 1 to all existing genome notes
    op.execute(
        """
        UPDATE genome_note
        SET version = 1
        WHERE version IS NULL
        """
    )

    # Populate note_url with placeholder for existing records (if any)
    op.execute(
        """
        UPDATE genome_note
        SET note_url = 'https://placeholder.url'
        WHERE note_url IS NULL
        """
    )

    # Now make assembly_id, version, and note_url NOT NULL
    op.alter_column("genome_note", "assembly_id", nullable=False)
    op.alter_column("genome_note", "version", nullable=False)
    op.alter_column("genome_note", "note_url", nullable=False)

    # Add foreign key constraint for assembly_id
    op.create_foreign_key(
        "fk_genome_note_assembly_id",
        "genome_note",
        "assembly",
        ["assembly_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Add unique constraint on (organism_key, version)
    op.create_unique_constraint(
        "uq_genome_note_organism_version",
        "genome_note",
        ["organism_key", "version"],
    )

    # Create indexes for efficient lookups
    op.create_index(
        "idx_genome_note_organism_key",
        "genome_note",
        ["organism_key"],
    )
    op.create_index(
        "idx_genome_note_assembly_id",
        "genome_note",
        ["assembly_id"],
    )
    op.create_index(
        "idx_genome_note_published",
        "genome_note",
        ["organism_key", "is_published"],
        postgresql_where=sa.text("is_published = TRUE"),
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_genome_note_published", table_name="genome_note")
    op.drop_index("idx_genome_note_assembly_id", table_name="genome_note")
    op.drop_index("idx_genome_note_organism_key", table_name="genome_note")

    # Drop unique constraint
    op.drop_constraint("uq_genome_note_organism_version", "genome_note", type_="unique")

    # Drop foreign key constraint
    op.drop_constraint("fk_genome_note_assembly_id", "genome_note", type_="foreignkey")

    # Drop new columns
    op.drop_column("genome_note", "published_at")
    op.drop_column("genome_note", "note_url")
    op.drop_column("genome_note", "version")
    op.drop_column("genome_note", "assembly_id")

    # Add back the old column
    op.add_column(
        "genome_note",
        sa.Column(
            "genome_note_assembly_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # Recreate the genome_note_assembly junction table
    op.create_table(
        "genome_note_assembly",
        sa.Column("genome_note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assembly_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["genome_note_id"],
            ["genome_note.id"],
        ),
        sa.ForeignKeyConstraint(
            ["assembly_id"],
            ["assembly.id"],
        ),
        sa.PrimaryKeyConstraint("genome_note_id", "assembly_id"),
    )
