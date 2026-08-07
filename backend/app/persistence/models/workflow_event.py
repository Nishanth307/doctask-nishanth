from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base
from app.core.constants import WorkflowStage
from app.persistence.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.persistence.models.run import Run


class WorkflowEvent(UUIDMixin, TimestampMixin, Base):
    """Records an event that occurred during a workflow run.

    Used by the frontend to display the workflow timeline and by the backend
    for audit/debugging purposes.
    """

    __tablename__ = "workflow_events"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    stage: Mapped[WorkflowStage] = mapped_column(
        Enum(
            WorkflowStage,
            name="workflow_stage",
            create_type=False,
        ),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    run: Mapped[Run] = relationship(
        back_populates="workflow_events",
    )

    def __repr__(self) -> str:
        return (
            f"WorkflowEvent(" f"stage='{self.stage.value}', " f"status='{self.status}')"
        )
