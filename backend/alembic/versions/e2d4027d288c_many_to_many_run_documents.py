"""many_to_many_run_documents

Revision ID: e2d4027d288c
Revises: 78238816e7be
Create Date: 2026-08-16 16:31:53.419018

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e2d4027d288c'
down_revision: Union[str, Sequence[str], None] = '78238816e7be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('run_documents',
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('run_id', 'document_id')
    )
    op.create_index(op.f('ix_run_documents_document_id'), 'run_documents', ['document_id'], unique=False)
    op.create_index(op.f('ix_run_documents_run_id'), 'run_documents', ['run_id'], unique=False)
    
    # Migrate existing associations
    op.execute(
        "INSERT INTO run_documents (run_id, document_id) SELECT run_id, id FROM documents WHERE run_id IS NOT NULL"
    )

    op.alter_column('documents', 'run_id',
               existing_type=sa.UUID(),
               nullable=True)
    op.drop_constraint(op.f('documents_run_id_fkey'), 'documents', type_='foreignkey')
    op.create_foreign_key(None, 'documents', 'runs', ['run_id'], ['id'], ondelete='SET NULL')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, 'documents', type_='foreignkey')
    op.create_foreign_key(op.f('documents_run_id_fkey'), 'documents', 'runs', ['run_id'], ['id'], ondelete='CASCADE')
    op.alter_column('documents', 'run_id',
               existing_type=sa.UUID(),
               nullable=False)
    op.drop_index(op.f('ix_run_documents_run_id'), table_name='run_documents')
    op.drop_index(op.f('ix_run_documents_document_id'), table_name='run_documents')
    op.drop_table('run_documents')
    # ### end Alembic commands ###
