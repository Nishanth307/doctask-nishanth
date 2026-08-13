from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models.workflow_result import WorkflowResult
from app.persistence.repositories.base import BaseRepository


class WorkflowResultRepository(
    BaseRepository[WorkflowResult]
):
    def __init__(self, db: Session) -> None:
        super().__init__(db, WorkflowResult)

    def get_by_run_id(
        self,
        run_id: UUID,
    ) -> WorkflowResult | None:
        statement = (
            select(WorkflowResult)
            .where(WorkflowResult.run_id == run_id)
        )

        return self.db.scalar(statement)