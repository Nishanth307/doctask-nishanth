from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base
from app.core.constants import RunStatus, WorkflowStage
from app.persistence.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.persistence.models.document import Document
    from app.persistence.models.finding import Finding
    from app.persistence.models.report import Report
    from app.persistence.models.workflow_event import WorkflowEvent


class Run(UUIDMixin, TimestampMixin, Base):
    """Represents one execution of the document workflow."""

    __tablename__ = "runs"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    thread_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )

    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus),
        default=RunStatus.PENDING,
        nullable=False,
    )

    stage: Mapped[WorkflowStage] = mapped_column(
        Enum(WorkflowStage, name="workflow_stage"),
        default=WorkflowStage.INGESTION,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    documents: Mapped[list[Document]] = relationship(
        back_populates="run", cascade="all,delete-orphan"
    )

    findings: Mapped[list[Finding]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    workflow_events: Mapped[list[WorkflowEvent]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="WorkflowEvent.created_at",
    )

    report: Mapped[Report | None] = relationship(
        back_populates="run",
        cascade="all,delete-orphan",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"Run(id={self.id}, " f"name={self.name!r}, " f"status={self.status!r})"
