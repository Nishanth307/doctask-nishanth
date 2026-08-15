"""add is_rules column

Revision ID: a54e938127de
Revises: 730cf93b7fa8
Create Date: 2026-08-15 16:39:43.016983

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a54e938127de'
down_revision: Union[str, Sequence[str], None] = '730cf93b7fa8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('is_rules', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('documents', 'is_rules')
