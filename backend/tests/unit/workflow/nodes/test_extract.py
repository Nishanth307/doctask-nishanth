from unittest.mock import MagicMock

from app.llm.enums import ModelName
from app.llm.schemas import (
    ClassificationResult,
    DocumentCategory,
    ExtractedFact,
    ExtractionResult,
)
from app.workflow.nodes.extract import ExtractNode


class TestExtractNode:

    def test_extract_success(self):
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
                ExtractedFact(
                    field="party_b",
                    value="XYZ Ltd",
                    confidence=0.92,
                ),
            ]
        )

        node = ExtractNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [
                {
                    "text": "Agreement between ABC Ltd and XYZ Ltd."
                }
            ],
            "classification": ClassificationResult(
                document_type=DocumentCategory.CONTRACT,
                confidence=0.95,
                reasoning="contract",
            ),
            "extracted_facts": [],
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert len(result["extracted_facts"]) == 2
        assert result["extracted_facts"][0]["field"] == "party_a"
        assert result["extracted_facts"][0]["value"] == "ABC Ltd"
        assert result["extracted_facts"][1]["field"] == "party_b"
        assert result["error"] is None

    def test_extract_uses_model_factory(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExtractionResult(
            facts=[]
        )

        node = ExtractNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Some document"}],
            "classification": ClassificationResult(
                document_type=DocumentCategory.REPORT,
                confidence=0.95,
                reasoning="report",
            ),
            "extracted_facts": [],
            "error": None,
        }

        # Act
        node(state)

        # Assert
        model_factory.create_model.assert_called_once_with(
            ModelName.GEMINI_2_5_FLASH,
        )

    def test_extract_uses_structured_output(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExtractionResult(
            facts=[]
        )

        node = ExtractNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Some document"}],
            "classification": ClassificationResult(
                document_type=DocumentCategory.CONTRACT,
                confidence=0.95,
                reasoning="contract",
            ),
            "extracted_facts": [],
            "error": None,
        }

        # Act
        node(state)

        # Assert
        model.with_structured_output.assert_called_once_with(
            ExtractionResult,
        )

    def test_extract_prompt_contains_document_type(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExtractionResult(
            facts=[]
        )

        node = ExtractNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Contract content"}],
            "classification": ClassificationResult(
                document_type=DocumentCategory.CONTRACT,
                confidence=0.95,
                reasoning="contract",
            ),
            "extracted_facts": [],
            "error": None,
        }

        # Act
        node(state)

        # Assert
        prompt = structured_model.invoke.call_args.args[0]

        assert "contract" in prompt
        assert "Contract content" in prompt

    def test_extract_handles_empty_result(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExtractionResult(
            facts=[]
        )

        node = ExtractNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "No useful information"}],
            "classification": ClassificationResult(
                document_type=DocumentCategory.OTHER,
                confidence=0.95,
                reasoning="other",
            ),
            "extracted_facts": [],
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["extracted_facts"] == []
        assert result["error"] is None

    def test_extract_propagates_model_exception(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.side_effect = RuntimeError(
            "LLM unavailable"
        )

        node = ExtractNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Some document"}],
            "classification": ClassificationResult(
                document_type=DocumentCategory.CONTRACT,
                confidence=0.95,
                reasoning="contract",
            ),
            "extracted_facts": [],
            "error": None,
        }

        # Act & Assert
        try:
            node(state)
        except RuntimeError as exc:
            assert str(exc) == "LLM unavailable"
        else:
            raise AssertionError("Expected RuntimeError")