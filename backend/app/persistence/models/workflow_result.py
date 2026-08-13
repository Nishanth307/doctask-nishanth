from uuid import UUID, uuid4

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base
from app.persistence.models.mixins import TimestampMixin


class WorkflowResult(TimestampMixin, Base):
    __tablename__ = "workflow_results"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    classification: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    extracted_facts: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
    )

    reconciliation: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    examination: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    human_decision: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )