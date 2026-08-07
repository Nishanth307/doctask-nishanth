from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base
from app.persistence.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.persistence.models.run import Run


class Report(UUIDMixin, TimestampMixin, Base):
    """Final generated report for a workflow run."""

    __tablename__ = "reports"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    run: Mapped[Run] = relationship(
        back_populates="report",
    )

    def __repr__(self) -> str:
        return (
            f"Report("
            f"run_id={self.run_id}, "
            f"version={self.version}, "
            f"approved={self.approved})"
        )
