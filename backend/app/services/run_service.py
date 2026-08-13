from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.core.constants import RunStatus, WorkflowStage
from app.persistence.models.run import Run
from app.persistence.repositories.run import RunRepository
from app.services.workflow_result_service import WorkflowResultService
from app.workflow.service import WorkflowService


class RunService:
    """
    Business logic related to workflow runs.
    """

    def __init__(
        self,
        repository: RunRepository,
        workflow_service: WorkflowService | None = None,
        workflow_result_service: WorkflowResultService | None = None,
    ) -> None:
        self.repository = repository
        self.workflow_service = workflow_service
        self.workflow_result_service = workflow_result_service

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
        run.completed_at = None
        run.error_message = None
        return run

    def wait_for_review(self, run: Run) -> Run:
        run.status = RunStatus.WAITING_FOR_REVIEW
        run.stage = WorkflowStage.REVIEW
        return run

    def complete_run(self, run: Run) -> Run:
        run.status = RunStatus.COMPLETED
        run.stage = WorkflowStage.COMMIT
        run.completed_at = datetime.now(timezone.utc)
        return run

    def fail_run(
        self,
        run: Run,
        error_message: str,
    ) -> Run:
        run.status = RunStatus.FAILED
        run.error_message = error_message
        return run

    def start_workflow(self, run: Run) -> dict[str, Any]:
        if self.workflow_service is None:
            raise RuntimeError(
                "WorkflowService is not configured"
            )

        self.start_run(run)

        result = self.workflow_service.start(
            state={
                "run_id": run.id,
            },
            thread_id=run.thread_id or str(run.id),
        )

        run.thread_id = result["thread_id"]
        state = result["state"]

        if state.get("status") == "failed":
            self.fail_run(
                run,
                state.get("error", "Workflow failed"),
            )

        elif state.get("human_review_required"):
            self.wait_for_review(run)

        elif state.get("status") == "completed":
            self.complete_run(run)

            if self.workflow_result_service is None:
                raise RuntimeError(
                    "WorkflowResultService is not configured"
                )
            self.workflow_result_service.create_result(
                run_id=run.id,
                state=state,
            )

        return result

    def resume_workflow(
        self,
        run: Run,
        decision: str,
    ) -> dict[str, Any]:
        if self.workflow_service is None:
            raise RuntimeError(
                "WorkflowService is not configured"
            )

        if not run.thread_id:
            raise ValueError(
                "Run does not have a workflow thread"
            )

        if run.status != RunStatus.WAITING_FOR_REVIEW:
            raise ValueError(
                "Run is not waiting for human review"
            )

        result = self.workflow_service.resume(
            thread_id=run.thread_id,
            decision=decision,
        )

        state = result["state"]

        if state.get("status") == "failed":
            self.fail_run(
                run,
                state.get("error", "Workflow failed"),
            )

        elif state.get("status") == "completed":
            self.complete_run(run)

            if self.workflow_result_service is None:
                raise RuntimeError(
                    "WorkflowResultService is not configured"
                )
            self.workflow_result_service.create_result(
                run_id=run.id,
                state=state,
            )

        elif state.get("human_review_required"):
            self.wait_for_review(run)

        else:
            run.status = RunStatus.RUNNING

        return result