from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.constants import RunStatus, WorkflowStage
from app.persistence.models.run import Run
from app.persistence.repositories.run import RunRepository
from app.services.run_service import RunService


class TestRunService:

    def setup_method(self):
        from app.persistence.repositories.finding import FindingRepository
        from app.persistence.repositories.report import ReportRepository
        from app.persistence.repositories.workflow_event import WorkflowEventRepository
        from app.persistence.repositories.workflow_result import WorkflowResultRepository
        from app.services.workflow_event_service import WorkflowEventService
        from app.services.workflow_result_service import WorkflowResultService
        from app.workflow.service import WorkflowService

        self.repository = Mock(spec=RunRepository)
        self.repository.create.side_effect = lambda x: x

        self.workflow_service = Mock(
            spec=WorkflowService,
        )

        self.workflow_result_service = Mock(
            spec=WorkflowResultService,
        )

        self.workflow_event_service = Mock(
            spec=WorkflowEventService,
        )

        self.finding_repository = Mock(spec=FindingRepository)
        self.report_repository = Mock(spec=ReportRepository)
        self.workflow_event_repository = Mock(spec=WorkflowEventRepository)
        self.workflow_result_repository = Mock(spec=WorkflowResultRepository)

        self.service = RunService(
            repository=self.repository,
            workflow_service=self.workflow_service,
            workflow_result_service=self.workflow_result_service,
            workflow_event_service=self.workflow_event_service,
            finding_repository=self.finding_repository,
            report_repository=self.report_repository,
            workflow_event_repository=self.workflow_event_repository,
            workflow_result_repository=self.workflow_result_repository,
        )

    def test_create_run_with_valid_name(self):
        # Arrange
        name = "Contract Review"

        expected_run = Run(
            name=name,
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )

        self.repository.create.return_value = expected_run

        # Act
        result = self.service.create_run(name)

        # Assert
        assert result.name == name
        assert result.status == RunStatus.PENDING
        assert result.stage == WorkflowStage.INGESTION

        self.repository.create.assert_called_once()
        
    def test_create_run_with_empty_name(self):
        # Arrange
        name = ""

        # Act
        result = self.service.create_run(name)

        # Assert
        assert result.name == ""
        assert result.status == RunStatus.PENDING
        assert result.stage == WorkflowStage.INGESTION

        self.repository.create.assert_called_once()

    def test_create_run_with_very_long_name(self):
        # Arrange
        name = "A" * 1000

        # Act
        result = self.service.create_run(name)

        # Assert
        assert result.name == name
        assert result.status == RunStatus.PENDING
        assert result.stage == WorkflowStage.INGESTION

        self.repository.create.assert_called_once()

    def test_create_run_when_repository_fails(self):
        # Arrange
        self.repository.create.side_effect = RuntimeError(
            "Database error"
        )

        # Act & Assert
        with pytest.raises(RuntimeError, match="Database error"):
            self.service.create_run("Contract Review")

        self.repository.create.assert_called_once()

    def test_get_existing_run(self):
        # Arrange
        run_id = uuid4()

        expected_run = Run(
            id=run_id,
            name="Contract Review",
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )

        self.repository.get_by_id.return_value = expected_run

        # Act
        result = self.service.get_run(run_id)

        # Assert
        assert result is expected_run
        assert result.id == run_id

        self.repository.get_by_id.assert_called_once_with(run_id)

    def test_get_run_when_run_does_not_exist(self):
        # Arrange
        run_id = uuid4()

        self.repository.get_by_id.return_value = None

        # Act
        result = self.service.get_run(run_id)

        # Assert
        assert result is None

        self.repository.get_by_id.assert_called_once_with(run_id)

    def test_get_run_when_repository_fails(self):
        # Arrange
        run_id = uuid4()

        self.repository.get_by_id.side_effect = RuntimeError(
            "Database unavailable"
        )

        # Act & Assert
        with pytest.raises(
            RuntimeError,
            match="Database unavailable",
        ):
            self.service.get_run(run_id)

        self.repository.get_by_id.assert_called_once_with(run_id)

    def test_start_pending_run(self):
        # Arrange
        run = Run(
            name="Contract Review",
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )

        # Act
        result = self.service.start_run(run)

        # Assert
        assert result is run
        assert result.status == RunStatus.RUNNING
        assert result.stage == WorkflowStage.INGESTION

    def test_start_failed_run(self):
        # Arrange
        run = Run(
            name="Contract Review",
            status=RunStatus.FAILED,
            stage=WorkflowStage.INGESTION,
            error_message="Previous failure",
        )

        # Act
        result = self.service.start_run(run)

        # Assert
        assert result.status == RunStatus.RUNNING
        assert result.stage == WorkflowStage.INGESTION
        assert result.error_message is None
        assert result.completed_at is None

    def test_complete_run(self):
        # Arrange
        run = Run(
            name="Contract Review",
            status=RunStatus.RUNNING,
            stage=WorkflowStage.EXAMINATION,
        )

        # Act
        result = self.service.complete_run(run)

        # Assert
        assert result is run
        assert result.status == RunStatus.COMPLETED
        assert result.stage == WorkflowStage.COMMIT
        assert result.completed_at is not None

    def test_wait_for_review(self):
        # Arrange
        run = Run(
            name="Contract Review",
            status=RunStatus.RUNNING,
            stage=WorkflowStage.RECONCILIATION,
        )

        # Act
        result = self.service.wait_for_review(run)

        # Assert
        assert result is run
        assert result.status == RunStatus.WAITING_FOR_REVIEW
        assert result.stage == WorkflowStage.REVIEW

    def test_fail_run(self):
        # Arrange
        run = Run(
            name="Contract Review",
            status=RunStatus.RUNNING,
            stage=WorkflowStage.EXTRACTION,
        )

        error_message = "Document extraction failed"

        # Act
        result = self.service.fail_run(
            run,
            error_message,
        )

        # Assert
        assert result is run
        assert result.status == RunStatus.FAILED
        assert result.error_message == error_message

    def test_fail_run_with_empty_error_message(self):
        # Arrange
        run = Run(
            name="Contract Review",
            status=RunStatus.RUNNING,
            stage=WorkflowStage.EXTRACTION,
        )

        # Act
        result = self.service.fail_run(run, "")

        # Assert
        assert result.status == RunStatus.FAILED
        assert result.error_message == ""

    def test_start_workflow_completes_run(self):
        run = Run(
            name="Contract Review",
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )

        workflow_result = {
            "thread_id": "thread-123",
            "state": {
                "status": "completed",
                "classification": {},
                "extracted_facts": [],
                "human_review_required": False,
            },
        }

        self.workflow_service.start.return_value = workflow_result

        result = self.service.start_workflow(run)

        assert result == workflow_result
        assert run.thread_id == "thread-123"
        assert run.status == RunStatus.COMPLETED

        self.workflow_service.start.assert_called_once()

        self.workflow_result_service.create_result.assert_called_once_with(
            run_id=run.id,
            state=workflow_result["state"],
        )

    def test_start_workflow_waits_for_human_review(self):
        run = Run(
            name="Contract Review",
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )

        workflow_result = {
            "thread_id": "thread-123",
            "state": {
                "human_review_required": True,
                "status": None,
            },
        }

        self.workflow_service.start.return_value = workflow_result

        result = self.service.start_workflow(run)

        assert result == workflow_result
        assert run.thread_id == "thread-123"
        assert run.status == RunStatus.WAITING_FOR_REVIEW
        assert run.stage == WorkflowStage.REVIEW

        self.workflow_result_service.create_result.assert_not_called()

    def test_resume_workflow_completes_run(self):
        run = Run(
            name="Contract Review",
            status=RunStatus.WAITING_FOR_REVIEW,
            stage=WorkflowStage.REVIEW,
            thread_id="thread-123",
        )

        workflow_result = {
            "thread_id": "thread-123",
            "state": {
                "status": "completed",
                "human_decision": "approve",
                "human_review_required": True,
            },
        }

        self.workflow_service.resume.return_value = workflow_result

        result = self.service.resume_workflow(
            run,
            "approve",
        )

        assert result == workflow_result
        assert run.status == RunStatus.COMPLETED
        assert run.stage == WorkflowStage.COMMIT

        self.workflow_service.resume.assert_called_once_with(
            thread_id="thread-123",
            decision="approve",
        )

        self.workflow_result_service.create_result.assert_called_once_with(
            run_id=run.id,
            state=workflow_result["state"],
        )

    def test_resume_workflow_requires_thread_id(self):
        run = Run(
            name="Contract Review",
            status=RunStatus.WAITING_FOR_REVIEW,
            stage=WorkflowStage.REVIEW,
        )

        with pytest.raises(
            ValueError,
            match="Run does not have a workflow thread",
        ):
            self.service.resume_workflow(
                run,
                "approve",
            )

    def test_resume_workflow_requires_waiting_status(self):
        run = Run(
            name="Contract Review",
            status=RunStatus.RUNNING,
            stage=WorkflowStage.EXAMINATION,
            thread_id="thread-123",
        )

        with pytest.raises(
            ValueError,
            match="Run is not waiting for human review",
        ):
            self.service.resume_workflow(
                run,
                "approve",
            )

    def test_start_workflow_without_workflow_service(self):
        # Arrange
        run = Run(
            id=uuid4(),
            name="Contract Review",
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )
        service_without_workflow = RunService(self.repository)

        # Act / Assert
        with pytest.raises(
            RuntimeError,
            match="WorkflowService is not configured",
        ):
            service_without_workflow.start_workflow(run)

    def test_resume_workflow_without_workflow_service(self):
        # Arrange
        run = Run(
            id=uuid4(),
            name="Contract Review",
            status=RunStatus.RUNNING,
            stage=WorkflowStage.RECONCILIATION,
        )
        service_without_workflow = RunService(self.repository)

        # Act / Assert
        with pytest.raises(
            RuntimeError,
            match="WorkflowService is not configured",
        ):
            service_without_workflow.resume_workflow(
                run,
                "approve",
            )

    def test_start_workflow_records_started_event(self):
        run = Run(
            id=uuid4(),
            name="Contract Review",
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )

        self.workflow_service.start.return_value = {
            "thread_id": "thread-123",
            "state": {
                "status": "completed",
            },
        }

        self.service.start_workflow(run)

        self.workflow_event_service.record.assert_any_call(
            run_id=run.id,
            stage=WorkflowStage.INGESTION,
            status="started",
            message="Workflow started",
        )

    def test_start_workflow_records_review_event(self):
        run = Run(
            id=uuid4(),
            name="Contract Review",
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )

        self.workflow_service.start.return_value = {
            "thread_id": "thread-123",
            "state": {
                "human_review_required": True,
            },
        }

        self.service.start_workflow(run)

        self.workflow_event_service.record.assert_any_call(
            run_id=run.id,
            stage=WorkflowStage.REVIEW,
            status="waiting",
            message="Workflow is waiting for human review",
        )

        assert run.status == RunStatus.WAITING_FOR_REVIEW

    def test_start_workflow_records_completion_event(self):
        run = Run(
            id=uuid4(),
            name="Contract Review",
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )

        self.workflow_service.start.return_value = {
            "thread_id": "thread-123",
            "state": {
                "status": "completed",
            },
        }

        self.service.start_workflow(run)

        self.workflow_event_service.record.assert_any_call(
            run_id=run.id,
            stage=WorkflowStage.COMMIT,
            status="completed",
            message="Workflow completed successfully",
        )

    def test_start_workflow_records_failure_event(self):
        run = Run(
            id=uuid4(),
            name="Contract Review",
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )

        self.workflow_service.start.return_value = {
            "thread_id": "thread-123",
            "state": {
                "status": "failed",
                "error": "Classification failed",
            },
        }

        self.service.start_workflow(run)

        self.workflow_event_service.record.assert_any_call(
            run_id=run.id,
            stage=WorkflowStage.INGESTION,
            status="failed",
            message="Classification failed",
        )

        assert run.status == RunStatus.FAILED

    def test_resume_workflow_records_human_decision(self):
        run = Run(
            id=uuid4(),
            name="Contract Review",
            status=RunStatus.WAITING_FOR_REVIEW,
            stage=WorkflowStage.REVIEW,
            thread_id="thread-123",
        )

        self.workflow_service.resume.return_value = {
            "thread_id": "thread-123",
            "state": {
                "status": "completed",
            },
        }

        self.service.resume_workflow(
            run,
            "approve",
        )

        self.workflow_event_service.record.assert_any_call(
            run_id=run.id,
            stage=WorkflowStage.REVIEW,
            status="decision",
            message="Human decision: approve",
        )

    def test_get_run_details_returns_aggregated_data(self):
        # Arrange
        run_id = uuid4()
        run = Run(id=run_id, name="Test Run")
        self.repository.get_by_id.return_value = run

        findings = [Mock()]
        report = Mock()
        events = [Mock()]
        result = Mock()

        self.finding_repository.get_by_run_id.return_value = findings
        self.report_repository.get_by_run_id.return_value = report
        self.workflow_event_repository.get_by_run_id.return_value = events
        self.workflow_result_repository.get_by_run_id.return_value = result

        # Act
        details = self.service.get_run_details(run_id)

        # Assert
        assert details is not None
        assert details["run"] is run
        assert details["findings"] == findings
        assert details["report"] is report
        assert details["workflow_events"] == events
        assert details["workflow_result"] is result

        self.repository.get_by_id.assert_called_once_with(run_id)
        self.finding_repository.get_by_run_id.assert_called_once_with(run_id)
        self.report_repository.get_by_run_id.assert_called_once_with(run_id)
        self.workflow_event_repository.get_by_run_id.assert_called_once_with(run_id)
        self.workflow_result_repository.get_by_run_id.assert_called_once_with(run_id)

    def test_get_run_details_returns_none_when_run_not_found(self):
        # Arrange
        run_id = uuid4()
        self.repository.get_by_id.return_value = None

        # Act
        details = self.service.get_run_details(run_id)

        # Assert
        assert details is None
        self.repository.get_by_id.assert_called_once_with(run_id)

    def test_get_review_success_requires_review_true(self):
        # Arrange
        run_id = uuid4()
        run = Run(
            id=run_id,
            name="Test Run",
            status=RunStatus.WAITING_FOR_REVIEW,
            stage=WorkflowStage.REVIEW,
        )
        self.repository.get_by_id.return_value = run

        findings = [Mock()]
        self.finding_repository.get_pending_reviews.return_value = findings

        # Act
        review = self.service.get_review(run_id)

        # Assert
        assert review is not None
        assert review["run_id"] == run_id
        assert review["status"] == RunStatus.WAITING_FOR_REVIEW
        assert review["stage"] == WorkflowStage.REVIEW
        assert review["requires_review"] is True
        assert review["findings"] == findings

        self.repository.get_by_id.assert_called_once_with(run_id)
        self.finding_repository.get_pending_reviews.assert_called_once_with(run_id)

    def test_get_review_requires_review_false(self):
        # Arrange
        run_id = uuid4()
        run = Run(
            id=run_id,
            name="Test Run",
            status=RunStatus.RUNNING,
            stage=WorkflowStage.INGESTION,
        )
        self.repository.get_by_id.return_value = run

        self.finding_repository.get_pending_reviews.return_value = []

        # Act
        review = self.service.get_review(run_id)

        # Assert
        assert review is not None
        assert review["requires_review"] is False

    def test_get_review_returns_none_when_run_not_found(self):
        # Arrange
        run_id = uuid4()
        self.repository.get_by_id.return_value = None

        # Act
        review = self.service.get_review(run_id)

        # Assert
        assert review is None
        self.repository.get_by_id.assert_called_once_with(run_id)

    def test_get_runs_returns_all_runs(self):
        # Arrange
        expected_runs = [Mock(), Mock()]
        self.repository.get_all.return_value = expected_runs

        # Act
        runs = self.service.get_runs()

        # Assert
        assert runs == expected_runs
        self.repository.get_all.assert_called_once()