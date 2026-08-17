from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from langgraph.types import Command

from app.workflow.graph import build_workflow
from app.llm.schemas import ClassificationResult, DocumentCategory, ExtractionResult, ExtractedFact, ExaminationResult


class TestHumanReview:

    def _get_workflow(self):
        model_factory = MagicMock()
        model = MagicMock()

        def side_effect_with_structured_output(schema):
            mock_structured_model = MagicMock()
            if schema == ClassificationResult:
                mock_structured_model.invoke.return_value = ClassificationResult(
                    document_type=DocumentCategory.CONTRACT,
                    confidence=0.95,
                    reasoning="The document contains contractual terms.",
                )
            elif schema == ExtractionResult:
                mock_structured_model.invoke.return_value = ExtractionResult(
                    facts=[
                        ExtractedFact(field="party_a", value="ABC Ltd", confidence=0.50),
                    ]
                )
            elif schema == ExaminationResult:
                mock_structured_model.invoke.return_value = ExaminationResult(
                    is_valid=True,
                    confidence=0.95,
                    issues=[],
                    summary="The extracted information is consistent.",
                )
            return mock_structured_model

        model.with_structured_output.side_effect = side_effect_with_structured_output
        model_factory.create_model.return_value = model
        return build_workflow(model_factory)

    def test_workflow_interrupts_for_human_review(self):
        # Arrange
        workflow = self._get_workflow()

        run_id = uuid4()

        state = {
            "run_id": run_id,
            "document_ids": [],
            "documents": [{"filename": "doc.pdf", "text": "Contract text"}],
            "classification": {},
            "extracted_facts": [],
            "contradictions": [],
            "findings": [],
            "updates": [],
            "human_review_required": True,
            "human_decision": None,
            "retry_count": 0,
            "max_retries": 3,
            "error": None,
        }

        config = {
            "configurable": {
                "thread_id": str(run_id),
            }
        }

        # Act
        result = workflow.invoke(state, config)

        # Assert
        assert "__interrupt__" in result

        interrupt = result["__interrupt__"][0]

        assert interrupt.value["type"] == "human_review"
        assert interrupt.value["run_id"] == str(run_id)

    def test_workflow_resumes_after_human_approval(self):
        # Arrange
        workflow = self._get_workflow()

        run_id = uuid4()

        state = {
            "run_id": run_id,
            "document_ids": [],
            "documents": [{"filename": "doc.pdf", "text": "Contract text"}],
            "classification": {},
            "extracted_facts": [],
            "contradictions": [],
            "findings": [],
            "updates": [],
            "human_review_required": True,
            "human_decision": None,
            "retry_count": 0,
            "max_retries": 3,
            "error": None,
        }

        config = {
            "configurable": {
                "thread_id": str(run_id),
            }
        }

        # First execution → interrupt
        interrupted = workflow.invoke(state, config)

        assert "__interrupt__" in interrupted

        # Act → resume
        result = workflow.invoke(
            Command(resume="approve"),
            config,
        )

        # Assert
        assert result["human_decision"] == "approve"

    def test_workflow_resumes_after_human_rejection(self):
        # Arrange
        workflow = self._get_workflow()

        run_id = uuid4()

        state = {
            "run_id": run_id,
            "document_ids": [],
            "documents": [{"filename": "doc.pdf", "text": "Contract text"}],
            "classification": {},
            "extracted_facts": [],
            "contradictions": [],
            "findings": [],
            "updates": [],
            "human_review_required": True,
            "human_decision": None,
            "retry_count": 0,
            "max_retries": 3,
            "error": None,
        }

        config = {
            "configurable": {
                "thread_id": str(run_id),
            }
        }

        workflow.invoke(state, config)

        # Act
        result = workflow.invoke(
            Command(resume="reject"),
            config,
        )

        # Assert
        assert result["human_decision"] == "reject"