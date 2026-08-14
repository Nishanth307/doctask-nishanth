from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.core.constants import RunStatus, WorkflowStage
from app.persistence.models.run import Run
from app.persistence.repositories.run import RunRepository
from app.persistence.repositories.finding import FindingRepository
from app.persistence.repositories.report import ReportRepository
from app.persistence.repositories.workflow_event import WorkflowEventRepository
from app.persistence.repositories.workflow_result import WorkflowResultRepository
from app.services.workflow_event_service import WorkflowEventService
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
        workflow_event_service: WorkflowEventService | None = None,
        finding_repository: FindingRepository | None = None,
        report_repository: ReportRepository | None = None,
        workflow_event_repository: WorkflowEventRepository | None = None,
        workflow_result_repository: WorkflowResultRepository | None = None,
    ) -> None:
        self.repository = repository
        self.workflow_service = workflow_service
        self.workflow_result_service = workflow_result_service
        self.workflow_event_service = workflow_event_service
        self.finding_repository = finding_repository
        self.report_repository = report_repository
        self.workflow_event_repository = workflow_event_repository
        self.workflow_result_repository = workflow_result_repository

    def get_run_details(self, run_id: UUID) -> dict[str, Any] | None:
        run = self.repository.get_by_id(run_id)

        if run is None:
            return None

        findings = (
            self.finding_repository.get_by_run_id(run_id)
            if self.finding_repository
            else []
        )

        report = (
            self.report_repository.get_by_run_id(run_id)
            if self.report_repository
            else None
        )

        workflow_events = (
            self.workflow_event_repository.get_by_run_id(run_id)
            if self.workflow_event_repository
            else []
        )

        workflow_result = (
            self.workflow_result_repository.get_by_run_id(run_id)
            if self.workflow_result_repository
            else None
        )

        return {
            "run": run,
            "findings": findings,
            "report": report,
            "workflow_events": workflow_events,
            "workflow_result": workflow_result,
        }

    def get_review(self, run_id: UUID) -> dict[str, Any] | None:
        run = self.repository.get_by_id(run_id)

        if run is None:
            return None

        findings = (
            self.finding_repository.get_pending_reviews(run_id)
            if self.finding_repository
            else []
        )

        return {
            "run_id": run.id,
            "status": run.status,
            "stage": run.stage,
            "requires_review": run.status == RunStatus.WAITING_FOR_REVIEW,
            "findings": findings,
        }

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

    def _record_event(
        self,
        run: Run,
        stage: WorkflowStage,
        status: str,
        message: str | None = None,
    ) -> None:
        if self.workflow_event_service is None:
            return

        self.workflow_event_service.record(
            run_id=run.id,
            stage=stage,
            status=status,
            message=message,
        )

    def start_workflow(self, run: Run) -> dict[str, Any]:
        if self.workflow_service is None:
            raise RuntimeError(
                "WorkflowService is not configured"
            )

        self.start_run(run)

        self._record_event(
            run,
            WorkflowStage.INGESTION,
            "started",
            "Workflow started",
        )

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

            self._record_event(
                run,
                WorkflowStage.INGESTION,
                "failed",
                run.error_message,
            )

        elif state.get("human_review_required"):
            self.wait_for_review(run)

            self._record_event(
                run,
                WorkflowStage.REVIEW,
                "waiting",
                "Workflow is waiting for human review",
            )

        elif state.get("status") == "completed":
            self.complete_run(run)

            self._record_event(
                run,
                WorkflowStage.COMMIT,
                "completed",
                "Workflow completed successfully",
            )

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

        self._record_event(
            run,
            WorkflowStage.REVIEW,
            "decision",
            f"Human decision: {decision}",
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

            self._record_event(
                run,
                WorkflowStage.REVIEW,
                "failed",
                run.error_message,
            )

        elif state.get("status") == "completed":
            self.complete_run(run)

            self._record_event(
                run,
                WorkflowStage.COMMIT,
                "completed",
                "Workflow completed successfully after human review",
            )

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

            self._record_event(
                run,
                WorkflowStage.REVIEW,
                "waiting",
                "Workflow requires additional human review",
            )

        else:
            run.status = RunStatus.RUNNING

        return result