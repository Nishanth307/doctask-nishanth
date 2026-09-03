from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base
from app.persistence.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.persistence.models.run import Run


class Report(UUIDMixin, TimestampMixin, Base):
    """Final generated report for a workflow run.

    Contains two distinct outputs:
    1. Audit Report (content field): review summary, reviewer decisions, provenance.
    2. Final Document (final_content field): the actual edited contract text.
    """

    __tablename__ = "reports"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # --- Audit/Review Report ---
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

    # --- Final Document Artifact ---
    # The actual edited contract text (not the audit report)
    final_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Path to the exported final document file (if saved to disk/storage)
    final_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Post-Edit Validation ---
    validation_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    validation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Provenance & Change History ---
    # JSON list of change records: [{change_id, finding_id, original_value, new_value, ...}]
    change_history: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )

    # --- Unchanged Content Proof ---
    # JSON dict: {section_name: {before_hash: ..., after_hash: ..., changed: bool}}
    section_hashes: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )

    run: Mapped[Run] = relationship(
        back_populates="report",
    )

    def __repr__(self) -> str:
        return (
            f"Report("
            f"run_id={self.run_id}, "
            f"version={self.version}, "
            f"approved={self.approved}, "
            f"has_final_doc={self.final_content is not None})"
        )
