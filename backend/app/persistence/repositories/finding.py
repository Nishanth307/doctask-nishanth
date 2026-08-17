from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import FindingSeverity, ReviewDecision
from app.persistence.models.finding import Finding
from app.persistence.repositories.base import BaseRepository


class FindingRepository(BaseRepository[Finding]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Finding)

    def get_by_run_id(self, run_id: UUID | str) -> list[Finding]:
        uid = UUID(str(run_id)) if not isinstance(run_id, UUID) else run_id
        statement = (
            select(Finding)
            .where(Finding.run_id == uid)
            .order_by(Finding.created_at.asc())
        )
        return list(self.db.scalars(statement).all())

    def get_pending_reviews(self, run_id: UUID | str) -> list[Finding]:
        uid = UUID(str(run_id)) if not isinstance(run_id, UUID) else run_id
        statement = (
            select(Finding)
            .where(
                Finding.run_id == uid,
                Finding.review_decision == ReviewDecision.PENDING,
            )
            .order_by(Finding.severity.desc())
        )

        return list(self.db.scalars(statement).all())

    def get_by_severity(self, run_id: UUID | str, severity: FindingSeverity) -> list[Finding]:
        uid = UUID(str(run_id)) if not isinstance(run_id, UUID) else run_id
        statement = select(Finding).where(
            Finding.run_id == uid, Finding.severity == severity
        )

        return list(self.db.scalars(statement).all())

