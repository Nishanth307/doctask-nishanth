from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base
from app.core.constants import (
    ApplicationStatus,
    FindingSeverity,
    ReviewDecision,
    ValidationStatus,
)
from app.persistence.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.persistence.models.run import Run
    from app.persistence.models.document import Document


class Finding(UUIDMixin, TimestampMixin, Base):
    """Represents an observation produced by the workflow.

    Each actionable finding contains both the detected issue AND the proposed
    change, so the system can apply the edit when the reviewer approves it.

    Lifecycle:
        review_decision: PENDING → APPROVED or REJECTED
        application_status: PENDING → APPLIED (if approved) or REJECTED (if reviewer rejected)
        validation_status: PENDING → PASSED / FAILED (after post-edit re-check)
    """

    __tablename__ = "findings"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optional link to the specific source document
    document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
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

    # --- Human review decision ---
    review_decision: Mapped[ReviewDecision] = mapped_column(
        Enum(
            ReviewDecision,
            name="review_decision",
        ),
        nullable=False,
        default=ReviewDecision.PENDING,
    )

    # --- Canonical proposed change fields ---
    # The exact value as it appears in the source document
    original_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The value that would replace original_value if this finding is approved
    proposed_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Human-readable description: "36 months → 24 months"
    proposed_edit: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Where in the document this finding was detected (e.g. "Section 3.2, Payment Terms")
    source_location: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Mutation tracking ---
    application_status: Mapped[ApplicationStatus] = mapped_column(
        Enum(
            ApplicationStatus,
            name="application_status",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=ApplicationStatus.PENDING,
    )

    # --- Post-edit validation tracking ---
    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(
            ValidationStatus,
            name="validation_status",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=ValidationStatus.PENDING,
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

    document: Mapped[Document | None] = relationship(
        "Document",
        foreign_keys=[document_id],
    )

    def __repr__(self) -> str:
        return (
            f"Finding("
            f"title='{self.title}', "
            f"severity='{self.severity.value}', "
            f"decision='{self.review_decision.value}', "
            f"app='{self.application_status.value}')"
        )

    @property
    def has_proposed_change(self) -> bool:
        """True if this finding carries a specific proposed edit."""
        return self.original_value is not None and self.proposed_value is not None

    @property
    def change_summary(self) -> str | None:
        """Human-readable one-line change summary."""
        if self.proposed_edit:
            return self.proposed_edit
        if self.original_value and self.proposed_value:
            return f"{self.original_value} → {self.proposed_value}"
        return None
