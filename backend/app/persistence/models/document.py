from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base
from app.core.constants import DocumentType
from app.persistence.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.persistence.models.document_chunk import DocumentChunkModel
    from app.persistence.models.run import Run


class Document(UUIDMixin, TimestampMixin, Base):
    """Uploaded document belonging to a workflow run."""

    __tablename__ = "documents"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    file_type: Mapped[str] = mapped_column(
        String(25),
        nullable=False,
    )

    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_types"),
        default=DocumentType.UNKNOWN,
        nullable=False,
    )

    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[Run] = relationship(
        back_populates="documents",
    )

    chunks: Mapped[list[DocumentChunkModel]] = relationship(
        "DocumentChunkModel",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"Document("
            f"id={self.id!r}, "
            f"run_id={self.run_id!r}, "
            f"filename={self.filename!r}, "
            f"file_path={self.file_path!r}, "
            f"file_type={self.file_type!r})"
        )
