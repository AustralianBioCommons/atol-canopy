"""Convert timestamps to TIMESTAMPTZ and add broker indexes/checks."""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_timestamptz_and_broker_indexes"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Timestamp columns -> TIMESTAMPTZ (treat existing values as UTC)
    tables = {
        "users": ["created_at", "updated_at"],
        "refresh_token": ["expires_at", "created_at", "updated_at"],
        "organism": ["created_at", "updated_at"],
        "accession_registry": ["accepted_at", "created_at", "updated_at"],
        "project": ["submitted_at", "created_at", "updated_at"],
        "project_submission": [
            "submitted_at",
            "created_at",
            "updated_at",
            "lock_acquired_at",
            "lock_expires_at",
        ],
        "sample": ["created_at", "updated_at"],
        "sample_submission": [
            "submitted_at",
            "created_at",
            "updated_at",
            "lock_acquired_at",
            "lock_expires_at",
        ],
        "experiment": ["created_at", "updated_at"],
        "experiment_submission": [
            "submitted_at",
            "created_at",
            "updated_at",
            "lock_acquired_at",
            "lock_expires_at",
        ],
        "read": ["created_at", "updated_at"],
        "read_submission": ["created_at", "updated_at", "lock_acquired_at", "lock_expires_at"],
        "submission_attempt": ["lock_acquired_at", "lock_expires_at", "created_at", "updated_at"],
        "submission_event": ["at"],
        "assembly": ["created_at", "updated_at"],
        "assembly_submission": ["submitted_at", "created_at", "updated_at"],
        "assembly_file": ["created_at", "updated_at"],
        "genome_note": ["published_at", "created_at", "updated_at"],
        "bpa_initiative": ["created_at", "updated_at"],
    }

    for table, columns in tables.items():
        for col in columns:
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {col} TYPE TIMESTAMPTZ USING {col} AT TIME ZONE 'UTC'"
            )

    # Sample latitude/longitude checks
    op.execute(
        "ALTER TABLE sample ADD CONSTRAINT chk_sample_latitude CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90)"
    )
    op.execute(
        "ALTER TABLE sample ADD CONSTRAINT chk_sample_longitude CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180)"
    )

    # Broker and status indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_submission_status ON project_submission (status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_submission_lock_expires_at ON project_submission (lock_expires_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sample_submission_status ON sample_submission (status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sample_submission_lock_expires_at ON sample_submission (lock_expires_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_experiment_submission_status ON experiment_submission (status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_experiment_submission_lock_expires_at ON experiment_submission (lock_expires_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_read_submission_status ON read_submission (status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_read_submission_lock_expires_at ON read_submission (lock_expires_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_submission_attempt_status ON submission_attempt (status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_submission_attempt_lock_expires_at ON submission_attempt (lock_expires_at)"
    )


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_submission_attempt_lock_expires_at")
    op.execute("DROP INDEX IF EXISTS idx_submission_attempt_status")
    op.execute("DROP INDEX IF EXISTS idx_read_submission_lock_expires_at")
    op.execute("DROP INDEX IF EXISTS idx_read_submission_status")
    op.execute("DROP INDEX IF EXISTS idx_experiment_submission_lock_expires_at")
    op.execute("DROP INDEX IF EXISTS idx_experiment_submission_status")
    op.execute("DROP INDEX IF EXISTS idx_sample_submission_lock_expires_at")
    op.execute("DROP INDEX IF EXISTS idx_sample_submission_status")
    op.execute("DROP INDEX IF EXISTS idx_project_submission_lock_expires_at")
    op.execute("DROP INDEX IF EXISTS idx_project_submission_status")

    # Drop checks
    op.execute("ALTER TABLE sample DROP CONSTRAINT IF EXISTS chk_sample_longitude")
    op.execute("ALTER TABLE sample DROP CONSTRAINT IF EXISTS chk_sample_latitude")

    # Convert columns back to TIMESTAMP (drop tz)
    tables = {
        "users": ["created_at", "updated_at"],
        "refresh_token": ["expires_at", "created_at", "updated_at"],
        "organism": ["created_at", "updated_at"],
        "accession_registry": ["accepted_at", "created_at", "updated_at"],
        "project": ["submitted_at", "created_at", "updated_at"],
        "project_submission": [
            "submitted_at",
            "created_at",
            "updated_at",
            "lock_acquired_at",
            "lock_expires_at",
        ],
        "sample": ["created_at", "updated_at"],
        "sample_submission": [
            "submitted_at",
            "created_at",
            "updated_at",
            "lock_acquired_at",
            "lock_expires_at",
        ],
        "experiment": ["created_at", "updated_at"],
        "experiment_submission": [
            "submitted_at",
            "created_at",
            "updated_at",
            "lock_acquired_at",
            "lock_expires_at",
        ],
        "read": ["created_at", "updated_at"],
        "read_submission": ["created_at", "updated_at", "lock_acquired_at", "lock_expires_at"],
        "submission_attempt": ["lock_acquired_at", "lock_expires_at", "created_at", "updated_at"],
        "submission_event": ["at"],
        "assembly": ["created_at", "updated_at"],
        "assembly_submission": ["submitted_at", "created_at", "updated_at"],
        "assembly_file": ["created_at", "updated_at"],
        "genome_note": ["published_at", "created_at", "updated_at"],
        "bpa_initiative": ["created_at", "updated_at"],
    }

    for table, columns in tables.items():
        for col in columns:
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {col} TYPE TIMESTAMP USING {col}::timestamp"
            )
