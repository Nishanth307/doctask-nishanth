"""add_error_fields_to_workflow_events

Revision ID: d5e2390f4a13
Revises: c4f1e83b9a12
Create Date: 2026-09-04 07:33:00.000000

Add error_type, attempt, retryable, and checkpoint_id columns to workflow_events
for granular per-node error tracking and auditability.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d5e2390f4a13"
down_revision: Union[str, None] = "c4f1e83b9a12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflow_events",
        sa.Column("error_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "workflow_events",
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "workflow_events",
        sa.Column("retryable", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "workflow_events",
        sa.Column("checkpoint_id", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflow_events", "checkpoint_id")
    op.drop_column("workflow_events", "retryable")
    op.drop_column("workflow_events", "attempt")
    op.drop_column("workflow_events", "error_type")
