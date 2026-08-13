from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langgraph.types import Command

from app.llm.enums import ModelName
from app.llm.schemas import (
    ClassificationResult,
    DocumentCategory,
    ExaminationResult,
    ExtractionResult,
)
from app.workflow.graph import build_workflow


class TestWorkflowGraph:

    @pytest.fixture(autouse=True)
    def mock_workflow_result_repository(self, monkeypatch):
        mock_repo_cls = MagicMock()
        mock_repo_instance = MagicMock()
        persisted_mock = MagicMock()
        persisted_mock.id = uuid4()
        mock_repo_instance.create.return_value = persisted_mock
        mock_repo_cls.return_value = mock_repo_instance
        monkeypatch.setattr("app.workflow.graph.WorkflowResultRepository", mock_repo_cls)

    @pytest.fixture
    def model_factory(self):
        factory = MagicMock()

        model = MagicMock()
        structured_model = MagicMock()

        factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        factory._model = model
        factory._structured_model = structured_model

        return factory

    @pytest.fixture
    def graph(self, model_factory):
        return build_workflow(
            model_factory=model_factory,
        )

    def configure_successful_llm_responses(
        self,
        model_factory,
    ):
        structured_model = model_factory._structured_model

        structured_model.invoke.side_effect = [
            ClassificationResult(
                document_type=DocumentCategory.CONTRACT,
                confidence=0.95,
                reasoning="Standard contract",
            ),
            ExtractionResult(
                facts=[
                    {
                        "field": "party_a",
                        "value": "ABC Ltd",
                        "confidence": 0.95,
                    }
                ]
            ),
            ExaminationResult(
                is_valid=True,
                confidence=0.95,
                issues=[],
                summary="Document is valid.",
            ),
        ]

    def test_successful_workflow(
        self,
        graph,
        model_factory,
    ):
        # Arrange
        self.configure_successful_llm_responses(
            model_factory,
        )

        thread_id = str(uuid4())

        state = {
            "run_id": uuid4(),
            "documents": [
                {
                    "text": (
                        "Agreement between ABC Ltd and XYZ Ltd."
                    )
                }
            ],
            "retry_count": 0,
            "max_retries": 3,
            "human_review_required": False,
            "human_decision": None,
            "error": None,
        }

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        # Act
        result = graph.invoke(
            state,
            config=config,
        )

        # Assert
        assert result["classification"] is not None
        assert result["extracted_facts"]
        assert result["human_review_required"] is False
        assert result["examination"].is_valid is True
        assert result["status"] == "completed"

    def test_classification_retry(
        self,
        graph,
        model_factory,
    ):
        # Arrange
        structured_model = model_factory._structured_model

        structured_model.invoke.side_effect = [
            ClassificationResult(
                document_type=DocumentCategory.CONTRACT,
                confidence=0.95,
                reasoning="Contract document",
            )
        ]

        thread_id = str(uuid4())

        state = {
            "run_id": uuid4(),
            "documents": [
                {
                    "text": "Contract document",
                }
            ],
            "retry_count": 0,
            "max_retries": 3,
            "simulate_failure": True,
            "human_review_required": False,
            "human_decision": None,
            "error": None,
        }

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        # Act
        result = graph.invoke(
            state,
            config=config,
        )

        # Assert
        assert result["retry_count"] == 3
        assert result["error"] == "Classification failed"

    def test_classification_terminal_failure(
        self,
        graph,
        model_factory,
    ):
        # Arrange
        thread_id = str(uuid4())

        state = {
            "run_id": uuid4(),
            "documents": [
                {
                    "text": "Invalid document",
                }
            ],
            "retry_count": 0,
            "max_retries": 2,
            "simulate_failure": True,
            "human_review_required": False,
            "human_decision": None,
            "error": None,
        }

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        # Act
        result = graph.invoke(
            state,
            config=config,
        )

        # Assert
        assert result["retry_count"] == 2
        assert result["error"] == "Classification failed"

    def test_human_review_approval_resume(
        self,
        graph,
        model_factory,
    ):
        structured_model = model_factory._structured_model
        structured_model.invoke.side_effect = [
            ClassificationResult(
                document_type=DocumentCategory.CONTRACT,
                confidence=0.95,
                reasoning="Standard contract",
            ),
            ExtractionResult(
                facts=[
                    {
                        "field": "party_a",
                        "value": "ABC Ltd",
                        "confidence": 0.70,
                    }
                ]
            ),
            ExaminationResult(
                is_valid=True,
                confidence=0.95,
                issues=[],
                summary="Document is valid.",
            ),
        ]

        thread_id = str(uuid4())

        state = {
            "run_id": uuid4(),
            "documents": [
                {
                    "text": "Agreement requiring review.",
                }
            ],
            "retry_count": 0,
            "max_retries": 3,
            "human_review_required": True,
            "human_decision": None,
            "error": None,
        }

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        # First invocation should pause for human review.
        result = graph.invoke(
            state,
            config=config,
        )

        snapshot = graph.get_state(config)

        assert snapshot.next
        assert "human_review" in snapshot.next

        # Resume with human approval.
        result = graph.invoke(
            Command(resume="approve"),
            config=config,
        )

        assert result["human_decision"] == "approve"
        assert result["status"] == "completed"