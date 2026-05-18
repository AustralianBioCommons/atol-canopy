"""Initial schema load from frozen bootstrap SQL."""

from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "base_schema" / "0001_initial_schema.sql"
    op.execute(schema_path.read_text())


def downgrade() -> None:
    # Dropping everything can be dangerous; leave as no-op.
    pass
