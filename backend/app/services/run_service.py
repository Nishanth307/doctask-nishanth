from uuid import UUID

from app.core.constants import RunStatus, WorkflowStage
from app.persistence.models.run import Run
from app.persistence.repositories.run import RunRepository


class RunService:
    """
    Business logic related to workflow runs.
    """

    def __init__(self, repository: RunRepository) -> None:
        self.repository = repository

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

    def fail_run(self, run: Run, error_message: str) -> Run:
        run.status = RunStatus.FAILED
        run.error_message = error_message
        return run
