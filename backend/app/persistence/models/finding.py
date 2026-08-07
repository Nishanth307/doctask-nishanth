from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base
from app.core.constants import FindingSeverity, ReviewDecision
from app.persistence.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.persistence.models.run import Run


class Finding(UUIDMixin, TimestampMixin, Base):
    """Represents an observation produced by the workflow."""

    __tablename__ = "findings"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(
            FindingSeverity,
            name="finding_severity",
        ),
        nullable=False,
        default=FindingSeverity.INFO,
    )

    review_decision: Mapped[ReviewDecision] = mapped_column(
        Enum(
            ReviewDecision,
            name="review_decision",
        ),
        nullable=False,
        default=ReviewDecision.PENDING,
    )

    citation: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    finding_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )

    run: Mapped[Run] = relationship(
        back_populates="findings",
    )

    def __repr__(self) -> str:
        return (
            f"Finding("
            f"title='{self.title}', "
            f"severity='{self.severity.value}', "
            f"decision='{self.review_decision.value}')"
        )
