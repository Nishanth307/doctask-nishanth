"""document_lifecycle_fields

Revision ID: a90e2792c610
Revises: e2d4027d288c
Create Date: 2026-09-03 23:08:00.633665

Add canonical proposed-edit fields to findings table, and final document
artifact fields to reports table. This enables the system to:
  - Store original_value, proposed_value, proposed_edit per finding
  - Track application_status (pending/applied/rejected/failed) per finding
  - Track validation_status (pending/passed/failed/skipped) per finding
  - Store the actual final document text in reports.final_content
  - Store section-level SHA-256 hashes for unchanged-content proof
  - Store a provenance change_history audit log
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a90e2792c610'
down_revision: Union[str, Sequence[str], None] = 'e2d4027d288c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enums first
    application_status_enum = sa.Enum(
        'pending', 'applied', 'rejected', 'failed',
        name='application_status'
    )
    validation_status_enum = sa.Enum(
        'pending', 'passed', 'failed', 'skipped',
        name='validation_status'
    )
    application_status_enum.create(op.get_bind(), checkfirst=True)
    validation_status_enum.create(op.get_bind(), checkfirst=True)

    # --- findings table: canonical proposed-edit fields ---
    op.add_column('findings', sa.Column('document_id', sa.UUID(), nullable=True))
    op.add_column('findings', sa.Column('original_value', sa.Text(), nullable=True))
    op.add_column('findings', sa.Column('proposed_value', sa.Text(), nullable=True))
    op.add_column('findings', sa.Column('proposed_edit', sa.Text(), nullable=True))
    op.add_column('findings', sa.Column('source_location', sa.Text(), nullable=True))
    op.add_column('findings', sa.Column(
        'application_status',
        sa.Enum('pending', 'applied', 'rejected', 'failed', name='application_status'),
        nullable=False,
        server_default='pending',
    ))
    op.add_column('findings', sa.Column(
        'validation_status',
        sa.Enum('pending', 'passed', 'failed', 'skipped', name='validation_status'),
        nullable=False,
        server_default='pending',
    ))
    op.create_index('ix_findings_document_id', 'findings', ['document_id'], unique=False)
    op.create_foreign_key(
        'fk_findings_document_id',
        'findings', 'documents',
        ['document_id'], ['id'],
        ondelete='SET NULL',
    )

    # --- reports table: final document artifact + provenance fields ---
    op.add_column('reports', sa.Column('final_content', sa.Text(), nullable=True))
    op.add_column('reports', sa.Column('final_file_path', sa.Text(), nullable=True))
    op.add_column('reports', sa.Column('validation_passed', sa.Boolean(), nullable=True))
    op.add_column('reports', sa.Column('validation_summary', sa.Text(), nullable=True))
    op.add_column('reports', sa.Column('change_history', sa.JSON(), nullable=True))
    op.add_column('reports', sa.Column('section_hashes', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('reports', 'section_hashes')
    op.drop_column('reports', 'change_history')
    op.drop_column('reports', 'validation_summary')
    op.drop_column('reports', 'validation_passed')
    op.drop_column('reports', 'final_file_path')
    op.drop_column('reports', 'final_content')

    op.drop_constraint('fk_findings_document_id', 'findings', type_='foreignkey')
    op.drop_index('ix_findings_document_id', table_name='findings')
    op.drop_column('findings', 'validation_status')
    op.drop_column('findings', 'application_status')
    op.drop_column('findings', 'source_location')
    op.drop_column('findings', 'proposed_edit')
    op.drop_column('findings', 'proposed_value')
    op.drop_column('findings', 'original_value')
    op.drop_column('findings', 'document_id')

    sa.Enum(name='validation_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='application_status').drop(op.get_bind(), checkfirst=True)
