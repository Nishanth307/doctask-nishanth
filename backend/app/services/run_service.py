from uuid import UUID

from app.core.constants import RunStatus, WorkflowStage
from app.persistence.models.run import Run
from app.persistence.repositories.run import RunRepository
from app.workflow.service import WorkflowService


class RunService:
    """
    Business logic related to workflow runs.
    """

    def __init__(
        self,
        repository: RunRepository,
        workflow_service: WorkflowService | None = None,
    ) -> None:
        self.repository = repository
        self.workflow_service = workflow_service

    def create_run(self, name: str) -> Run:
        run = Run(
            name=name,
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )

        return self.repository.create(run)

    def get_run(self, run_id: UUID) -> Run | None:
        return self.repository.get_by_id(run_id)

    def start_run(self, run: Run) -> Run:
        run.status = RunStatus.RUNNING
        run.stage = WorkflowStage.INGESTION
        return run

    def complete_run(self, run: Run) -> Run:
        run.status = RunStatus.COMPLETED
        return run

    def fail_run(
        self,
        run: Run,
        error_message: str,
    ) -> Run:
        run.status = RunStatus.FAILED
        run.error_message = error_message
        return run

    def start_workflow(self, run: Run) -> dict:
        if self.workflow_service is None:
            raise RuntimeError(
                "WorkflowService is not configured"
            )

        self.start_run(run)

        state = {
            "run_id": run.id,
            "retry_count": 0,
            "max_retries": 3,
            "human_review_required": False,
            "human_decision": None,
            "error": None,
        }

        return self.workflow_service.start(
            state=state,
            thread_id=str(run.id),
        )

    def resume_workflow(
        self,
        run: Run,
        decision: str,
    ) -> dict:
        if self.workflow_service is None:
            raise RuntimeError(
                "WorkflowService is not configured"
            )

        return self.workflow_service.resume(
            thread_id=str(run.id),
            decision=decision,
        )