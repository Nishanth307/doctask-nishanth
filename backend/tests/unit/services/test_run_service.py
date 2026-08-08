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
        self.repository = Mock(spec=RunRepository)
        self.repository.create.side_effect = lambda x: x
        self.service = RunService(self.repository)

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
        assert result.error_message == "Previous failure"

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