from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models.document import Document
from app.persistence.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Document)

    def get_by_run_id(self, run_id: UUID) -> list[Document]:
        from app.persistence.models.run import Run
        statement = (
            select(Document)
            .join(Document.runs)
            .where(Run.id == run_id)
            .order_by(Document.created_at.asc())
        )

        return list(self.db.scalars(statement).all())

    def get_by_checksum(self, checksum: str) -> Document | None:
        statement = select(Document).where(Document.checksum == checksum)
        return self.db.scalar(statement)


# The checksum query will later help with:
# Upload document
#        ↓
# Calculate SHA-256
#        ↓
# Already exists?
#     ↙       ↘
#    Yes       No
#     ↓         ↓
# Skip       Process
