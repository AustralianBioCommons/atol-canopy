"""Update assembly schema with improved file handling and simplified submission

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-16 22:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename enum type and add new values
    op.execute("ALTER TYPE assembly_output_file_type RENAME TO assembly_output_file_type_old")
    op.execute("""
        CREATE TYPE assembly_file_type AS ENUM (
            'FASTA',
            'QC_REPORT',
            'STATISTICS',
            'OTHER'
        )
    """)
    
    # Rename table
    op.rename_table('assembly_output_file', 'assembly_file')
    
    # Update assembly_file table structure
    op.alter_column('assembly_file', 'type',
                    new_column_name='file_type',
                    type_=sa.Enum('FASTA', 'QC_REPORT', 'STATISTICS', 'OTHER', name='assembly_file_type'),
                    existing_type=sa.Enum('QC', 'Other', name='assembly_output_file_type_old'),
                    postgresql_using="CASE WHEN type::text = 'QC' THEN 'QC_REPORT'::assembly_file_type ELSE 'OTHER'::assembly_file_type END",
                    nullable=False)
    
    # Add new columns to assembly_file
    op.alter_column('assembly_file', 'assembly_id',
                    existing_type=postgresql.UUID(),
                    nullable=False)
    op.add_column('assembly_file', sa.Column('file_checksum_method', sa.Text(), nullable=True, server_default='MD5'))
    op.add_column('assembly_file', sa.Column('description', sa.Text(), nullable=True))
    
    # Create indexes for assembly_file
    op.create_index('idx_assembly_file_assembly_id', 'assembly_file', ['assembly_id'])
    op.create_index('idx_assembly_file_type', 'assembly_file', ['assembly_id', 'file_type'])
    
    # Drop old enum type
    op.execute("DROP TYPE assembly_output_file_type_old")
    
    # Update assembly table
    op.drop_column('assembly', 'fasta')
    op.add_column('assembly', sa.Column('description', sa.Text(), nullable=True))
    
    # Update assembly_submission table - drop old columns first
    op.drop_column('assembly_submission', 'assembly_name')
    op.drop_column('assembly_submission', 'organism_key')
    op.drop_column('assembly_submission', 'sample_id')
    op.drop_column('assembly_submission', 'internal_json')
    op.drop_column('assembly_submission', 'prepared_payload')
    op.drop_column('assembly_submission', 'returned_payload')
    
    # Add new columns to assembly_submission
    op.add_column('assembly_submission', sa.Column('sample_accession', sa.Text(), nullable=True))
    op.add_column('assembly_submission', sa.Column('project_accession', sa.Text(), nullable=True))
    op.add_column('assembly_submission', sa.Column('manifest_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('assembly_submission', sa.Column('submission_xml', sa.Text(), nullable=True))
    op.add_column('assembly_submission', sa.Column('response_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('assembly_submission', sa.Column('submitted_by', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Create foreign key for submitted_by
    op.create_foreign_key('fk_assembly_submission_user', 'assembly_submission', 'users', ['submitted_by'], ['id'])
    
    # Create unique index for accepted submissions
    op.execute("""
        CREATE UNIQUE INDEX uq_assembly_one_accepted
        ON assembly_submission (assembly_id, authority)
        WHERE status = 'accepted' AND accession IS NOT NULL
    """)


def downgrade() -> None:
    # Drop unique index
    op.drop_index('uq_assembly_one_accepted', table_name='assembly_submission')
    
    # Revert assembly_submission changes
    op.drop_constraint('fk_assembly_submission_user', 'assembly_submission', type_='foreignkey')
    op.drop_column('assembly_submission', 'submitted_by')
    op.drop_column('assembly_submission', 'response_payload')
    op.drop_column('assembly_submission', 'submission_xml')
    op.drop_column('assembly_submission', 'manifest_json')
    op.drop_column('assembly_submission', 'project_accession')
    op.drop_column('assembly_submission', 'sample_accession')
    
    op.add_column('assembly_submission', sa.Column('returned_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('assembly_submission', sa.Column('prepared_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('assembly_submission', sa.Column('internal_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('assembly_submission', sa.Column('sample_id', postgresql.UUID(), nullable=False))
    op.add_column('assembly_submission', sa.Column('organism_key', sa.Text(), nullable=False))
    op.add_column('assembly_submission', sa.Column('assembly_name', sa.Text(), nullable=False))
    
    # Revert assembly table
    op.drop_column('assembly', 'description')
    op.add_column('assembly', sa.Column('fasta', sa.String(length=255), nullable=False))
    
    # Recreate old enum
    op.execute("CREATE TYPE assembly_output_file_type AS ENUM ('QC', 'Other')")
    
    # Drop indexes
    op.drop_index('idx_assembly_file_type', table_name='assembly_file')
    op.drop_index('idx_assembly_file_assembly_id', table_name='assembly_file')
    
    # Revert assembly_file changes
    op.drop_column('assembly_file', 'description')
    op.drop_column('assembly_file', 'file_checksum_method')
    op.alter_column('assembly_file', 'assembly_id',
                    existing_type=postgresql.UUID(),
                    nullable=True)
    
    op.alter_column('assembly_file', 'file_type',
                    new_column_name='type',
                    type_=sa.Enum('QC', 'Other', name='assembly_output_file_type'),
                    existing_type=sa.Enum('FASTA', 'QC_REPORT', 'STATISTICS', 'OTHER', name='assembly_file_type'),
                    postgresql_using="CASE WHEN file_type::text = 'QC_REPORT' THEN 'QC'::assembly_output_file_type ELSE 'Other'::assembly_output_file_type END",
                    nullable=False)
    
    # Rename table back
    op.rename_table('assembly_file', 'assembly_output_file')
    
    # Drop new enum type
    op.execute("DROP TYPE assembly_file_type")
