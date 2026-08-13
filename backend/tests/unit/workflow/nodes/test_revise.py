from unittest.mock import MagicMock

from app.llm.enums import ModelName
from app.llm.schemas import (
    ExtractedFact,
    ExtractionResult,
)
from app.workflow.nodes.revise import ReviseNode


class TestReviseNode:

    def test_revise_success(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="party_a",
                    value="ABC Ltd",
                    confidence=0.95,
                ),
            ]
        )

        node = ReviseNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [
                {
                    "text": "Agreement between ABC Ltd and XYZ Ltd."
                }
            ],
            "extracted_facts": [
                {
                    "field": "party_a",
                    "value": "Unknown",
                    "confidence": 0.60,
                }
            ],
            "human_decision": "reject",
            "human_review_required": True,
            "retry_count": 0,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert len(result["extracted_facts"]) == 1
        assert result["extracted_facts"][0]["field"] == "party_a"
        assert result["extracted_facts"][0]["value"] == "ABC Ltd"
        assert result["error"] is None
        assert result["human_review_required"] is False

    def test_revise_uses_model_factory(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExtractionResult(
            facts=[]
        )

        node = ReviseNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Document"}],
            "extracted_facts": [],
            "human_decision": "reject",
            "error": None,
        }

        # Act
        node(state)

        # Assert
        model_factory.create_model.assert_called_once_with(
            ModelName.GEMINI_2_5_FLASH,
        )

    def test_revise_uses_structured_output(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExtractionResult(
            facts=[]
        )

        node = ReviseNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Document"}],
            "extracted_facts": [],
            "human_decision": "reject",
            "error": None,
        }

        # Act
        node(state)

        # Assert
        model.with_structured_output.assert_called_once_with(
            ExtractionResult,
        )

    def test_revise_prompt_contains_document_and_previous_facts(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExtractionResult(
            facts=[]
        )

        node = ReviseNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [
                {
                    "text": "ABC Ltd is the contracting party."
                }
            ],
            "extracted_facts": [
                {
                    "field": "party_a",
                    "value": "Unknown",
                    "confidence": 0.50,
                }
            ],
            "human_decision": "reject",
            "error": None,
        }

        # Act
        node(state)

        # Assert
        prompt = structured_model.invoke.call_args.args[0]

        assert "ABC Ltd is the contracting party." in prompt
        assert "party_a" in prompt
        assert "Unknown" in prompt
        assert "reject" in prompt

    def test_revise_handles_empty_result(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExtractionResult(
            facts=[]
        )

        node = ReviseNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Document"}],
            "extracted_facts": [],
            "human_decision": "reject",
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["extracted_facts"] == []
        assert result["error"] is None
        assert result["human_review_required"] is False

    def test_revise_converts_model_exception_to_error_state(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.side_effect = RuntimeError(
            "LLM unavailable"
        )

        node = ReviseNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Document"}],
            "extracted_facts": [],
            "human_decision": "reject",
            "retry_count": 0,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["error"] == "LLM unavailable"
        assert result["retry_count"] == 1