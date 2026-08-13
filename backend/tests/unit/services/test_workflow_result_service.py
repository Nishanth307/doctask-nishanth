from unittest.mock import Mock
from uuid import uuid4

from app.llm.schemas import (
    ClassificationResult,
    DocumentCategory,
    ExaminationResult,
)
from app.persistence.models.workflow_result import WorkflowResult
from app.persistence.repositories.workflow_result import (
    WorkflowResultRepository,
)
from app.services.workflow_result_service import WorkflowResultService


class TestWorkflowResultService:

    def setup_method(self):
        self.repository = Mock(
            spec=WorkflowResultRepository,
        )

        self.repository.create.side_effect = lambda result: result

        self.service = WorkflowResultService(
            self.repository,
        )

    def test_create_result(self):
        # Arrange
        run_id = uuid4()

        classification = ClassificationResult(
            document_type=DocumentCategory.CONTRACT,
            confidence=0.95,
            reasoning="Contractual terms were detected.",
        )

        examination = ExaminationResult(
            is_valid=True,
            confidence=0.92,
            issues=[],
            summary="The document is valid.",
        )

        state = {
            "status": "completed",
            "classification": classification,
            "extracted_facts": [
                {
                    "field": "party_a",
                    "value": "ABC Ltd",
                    "confidence": 0.95,
                }
            ],
            "human_review_required": False,
            "human_decision": None,
            "examination": examination,
        }

        # Act
        result = self.service.create_result(
            run_id,
            state,
        )

        # Assert
        assert isinstance(result, WorkflowResult)
        assert result.run_id == run_id
        assert result.status == "completed"

        assert result.classification == {
            "document_type": "contract",
            "confidence": 0.95,
            "reasoning": "Contractual terms were detected.",
        }

        assert result.extracted_facts == [
            {
                "field": "party_a",
                "value": "ABC Ltd",
                "confidence": 0.95,
            }
        ]

        assert result.reconciliation == {
            "human_review_required": False,
        }

        assert result.examination == {
            "is_valid": True,
            "confidence": 0.92,
            "issues": [],
            "summary": "The document is valid.",
        }

        assert result.human_decision is None

        self.repository.create.assert_called_once_with(
            result,
        )

    def test_create_result_with_human_decision(self):
        # Arrange
        run_id = uuid4()

        state = {
            "status": "completed",
            "classification": None,
            "extracted_facts": [],
            "human_review_required": True,
            "human_decision": "approve",
            "examination": None,
        }

        # Act
        result = self.service.create_result(
            run_id,
            state,
        )

        # Assert
        assert result.run_id == run_id
        assert result.human_decision == "approve"

        assert result.reconciliation == {
            "human_review_required": True,
        }

    def test_create_result_handles_missing_optional_state(self):
        # Arrange
        run_id = uuid4()

        state = {
            "status": "completed",
        }

        # Act
        result = self.service.create_result(
            run_id,
            state,
        )

        # Assert
        assert result.status == "completed"
        assert result.classification == {}
        assert result.extracted_facts == []
        assert result.reconciliation == {
            "human_review_required": False,
        }
        assert result.examination == {}
        assert result.human_decision is None

    def test_create_result_preserves_failed_status(self):
        # Arrange
        run_id = uuid4()

        state = {
            "status": "failed",
            "error": "Examination failed",
        }

        # Act
        result = self.service.create_result(
            run_id,
            state,
        )

        # Assert
        assert result.status == "failed"

    def test_get_result(self):
        # Arrange
        run_id = uuid4()

        expected = WorkflowResult(
            run_id=run_id,
            status="completed",
            classification={},
            extracted_facts=[],
            reconciliation={
                "human_review_required": False,
            },
            examination={},
            human_decision=None,
        )

        self.repository.get_by_run_id.return_value = expected

        # Act
        result = self.service.get_result(run_id)

        # Assert
        assert result is expected

        self.repository.get_by_run_id.assert_called_once_with(
            run_id,
        )

    def test_get_result_when_not_found(self):
        # Arrange
        run_id = uuid4()

        self.repository.get_by_run_id.return_value = None

        # Act
        result = self.service.get_result(run_id)

        # Assert
        assert result is None

        self.repository.get_by_run_id.assert_called_once_with(
            run_id,
        )

    def test_create_result_propagates_repository_error(self):
        # Arrange
        run_id = uuid4()

        self.repository.create.side_effect = RuntimeError(
            "Database error",
        )

        # Act & Assert
        try:
            self.service.create_result(
                run_id,
                {"status": "completed"},
            )
        except RuntimeError as exc:
            assert str(exc) == "Database error"
        else:
            raise AssertionError(
                "Expected RuntimeError"
            )
