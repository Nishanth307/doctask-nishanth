from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import RunStatus
from app.persistence.models import Run
from app.persistence.repositories.base import BaseRepository


class RunRepository(BaseRepository[Run]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Run)

    def get_by_status(self, status: RunStatus) -> list[Run]:
        statement = (
            select(Run).where(Run.status == status).order_by(Run.created_at.desc())
        )

        return list(self.db.scalars(statement).all())

    def get_with_documents(self, run_id: UUID) -> Run | None:
        return self.db.get(Run, run_id)

    def get_all(self) -> list[Run]:
        statement = (
            select(Run)
            .order_by(Run.created_at.desc())
        )

        return list(self.db.scalars(statement).all())


# The repository knows how to query Run, but it doesn't know why you're running the workflow.
# That's the service's responsibility.
