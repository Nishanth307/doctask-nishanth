from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models.report import Report
from app.persistence.repositories.base import BaseRepository


class ReportRepository(BaseRepository[Report]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Report)

    def get_by_run_id(self, run_id: UUID) -> Report | None:
        statement = select(Report).where(Report.run_id == run_id)

        return self.db.scalar(statement)
