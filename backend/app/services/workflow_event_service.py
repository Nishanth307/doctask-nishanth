from uuid import UUID

from app.core.constants import WorkflowStage
from app.persistence.models.workflow_event import WorkflowEvent
from app.persistence.repositories.workflow_event import (
    WorkflowEventRepository,
)


class WorkflowEventService:
    def __init__(
        self,
        repository: WorkflowEventRepository,
    ) -> None:
        self.repository = repository

    def record(
        self,
        run_id: UUID,
        stage: WorkflowStage,
        status: str,
        message: str | None = None,
        duration_ms: int | None = None,
    ) -> WorkflowEvent:
        event = WorkflowEvent(
            run_id=run_id,
            stage=stage,
            status=status,
            message=message,
            duration_ms=duration_ms,
        )

        return self.repository.create(event)

    def get_events(
        self,
        run_id: UUID,
    ) -> list[WorkflowEvent]:
        return self.repository.get_by_run_id(run_id)
