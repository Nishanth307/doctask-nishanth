from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import WorkflowStage
from app.persistence.models.workflow_event import WorkflowEvent
from app.persistence.repositories.base import BaseRepository


class WorkflowEventRepository(BaseRepository[WorkflowEvent]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, WorkflowEvent)

    def get_by_run_id(
        self,
        run_id: UUID,
    ) -> list[WorkflowEvent]:
        statement = (
            select(WorkflowEvent)
            .where(WorkflowEvent.run_id == run_id)
            .order_by(WorkflowEvent.created_at.asc())
        )

        return list(self.db.scalars(statement).all())

    def get_by_stage(
        self,
        run_id: UUID,
        stage: WorkflowStage,
    ) -> list[WorkflowEvent]:
        statement = (
            select(WorkflowEvent)
            .where(
                WorkflowEvent.run_id == run_id,
                WorkflowEvent.stage == stage,
            )
            .order_by(WorkflowEvent.created_at.asc())
        )

        return list(self.db.scalars(statement).all())
