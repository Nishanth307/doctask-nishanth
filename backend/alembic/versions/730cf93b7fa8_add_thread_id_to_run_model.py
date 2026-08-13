"""add thread_id to run model

Revision ID: 730cf93b7fa8
Revises: f1f64f328dcd
Create Date: 2026-08-13 17:33:43.838602

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '730cf93b7fa8'
down_revision: Union[str, Sequence[str], None] = 'f1f64f328dcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('runs', sa.Column('thread_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_runs_thread_id'), 'runs', ['thread_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_runs_thread_id'), table_name='runs')
    op.drop_column('runs', 'thread_id')
    # ### end Alembic commands ###
