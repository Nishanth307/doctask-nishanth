from unittest.mock import MagicMock

import pytest

from app.llm.enums import ModelName
from app.llm.schemas import ClassificationResult, DocumentCategory
from app.workflow.nodes.classify import ClassifyNode


class TestClassifyNode:

    def test_classify_success(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        classification = ClassificationResult(
            document_type=DocumentCategory.CONTRACT,
            confidence=0.95,
            reasoning="The document contains contractual terms.",
        )

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model
        structured_model.invoke.return_value = classification

        node = ClassifyNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [
                {
                    "text": "This agreement is entered into between Party A and Party B."
                }
            ],
            "classification": None,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["classification"] == classification
        assert result["error"] is None

    def test_classify_uses_model_factory(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model
        structured_model.invoke.return_value = ClassificationResult(
            document_type=DocumentCategory.INVOICE,
            confidence=0.90,
            reasoning="The document contains invoice information.",
        )

        node = ClassifyNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [
                {
                    "text": "Invoice number: INV-001"
                }
            ],
            "classification": None,
            "error": None,
        }

        # Act
        node(state)

        # Assert
        model_factory.create_model.assert_called_once_with(
            ModelName.GEMINI_2_5_FLASH
        )

    def test_classify_uses_structured_output(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ClassificationResult(
            document_type=DocumentCategory.REPORT,
            confidence=0.88,
            reasoning="The document contains report-style content.",
        )

        node = ClassifyNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Quarterly business report"}],
            "classification": None,
            "error": None,
        }

        # Act
        node(state)

        # Assert
        model.with_structured_output.assert_called_once_with(
            ClassificationResult
        )

    def test_classify_combines_multiple_documents(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ClassificationResult(
            document_type=DocumentCategory.CONTRACT,
            confidence=0.92,
            reasoning="Multiple documents contain contractual information.",
        )

        node = ClassifyNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [
                {"text": "First document"},
                {"text": "Second document"},
            ],
            "classification": None,
            "error": None,
        }

        # Act
        node(state)

        # Assert
        prompt = structured_model.invoke.call_args.args[0]

        assert "First document" in prompt
        assert "Second document" in prompt

    def test_classify_with_empty_documents(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ClassificationResult(
            document_type=DocumentCategory.OTHER,
            confidence=0.10,
            reasoning="No document content was provided.",
        )

        node = ClassifyNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [],
            "classification": None,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["classification"].document_type == DocumentCategory.OTHER
        structured_model.invoke.assert_called_once()

    def test_classify_propagates_model_exception(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.side_effect = RuntimeError(
            "LLM unavailable"
        )

        node = ClassifyNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Some document"}],
            "classification": None,
            "error": None,
        }

        # Act & Assert
        with pytest.raises(RuntimeError, match="LLM unavailable"):
            node(state)


def test_classification_rejects_invalid_confidence():
    with pytest.raises(ValueError):
        ClassificationResult(
            document_type=DocumentCategory.CONTRACT,
            confidence=1.5,
            reasoning="Invalid confidence.",
        )


def test_classification_rejects_negative_confidence():
    with pytest.raises(ValueError):
        ClassificationResult(
            document_type=DocumentCategory.CONTRACT,
            confidence=-0.1,
            reasoning="Invalid confidence.",
        )