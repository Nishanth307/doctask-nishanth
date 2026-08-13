from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.constants import RunStatus, WorkflowStage
from app.persistence.models.run import Run
from app.persistence.repositories.run import RunRepository
from app.services.run_service import RunService


class TestRunService:

    def setup_method(self):
        # Arrange
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

        self.service = RunService(
            repository=self.repository,
            workflow_service=self.workflow_service,
            workflow_result_service=self.workflow_result_service,
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