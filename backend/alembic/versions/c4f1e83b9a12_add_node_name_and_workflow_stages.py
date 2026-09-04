"""add_node_name_and_workflow_stages

Revision ID: c4f1e83b9a12
Revises: a90e2792c610
Create Date: 2026-09-04 07:10:00.000000

Add node_name column to workflow_events table for per-node event tracking.
Add new WorkflowStage enum values for generate_changes, findings_review,
apply_edits, validate_edits.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4f1e83b9a12"
down_revision: Union[str, None] = "a90e2792c610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add node_name column to workflow_events
    op.add_column(
        "workflow_events",
        sa.Column("node_name", sa.String(100), nullable=True),
    )

    # Add new enum values to the workflow_stage type
    # PostgreSQL requires ALTER TYPE for enum extensions
    workflow_stage_type = sa.Enum(
        "ingestion", "classification", "extraction", "reconciliation",
        "examination", "generate_changes", "findings_review", "apply_edits",
        "validate_edits", "update", "review", "commit",
        name="workflow_stage",
    )
    # Use raw SQL for adding enum values (idempotent with IF NOT EXISTS)
    op.execute("ALTER TYPE workflow_stage ADD VALUE IF NOT EXISTS 'generate_changes'")
    op.execute("ALTER TYPE workflow_stage ADD VALUE IF NOT EXISTS 'findings_review'")
    op.execute("ALTER TYPE workflow_stage ADD VALUE IF NOT EXISTS 'apply_edits'")
    op.execute("ALTER TYPE workflow_stage ADD VALUE IF NOT EXISTS 'validate_edits'")


def downgrade() -> None:
    op.drop_column("workflow_events", "node_name")
    # Note: PostgreSQL does not support removing enum values in a downgrade.
    # The extra enum values are harmless if unused.
