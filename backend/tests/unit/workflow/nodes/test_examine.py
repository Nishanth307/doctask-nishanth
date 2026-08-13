from unittest.mock import MagicMock

import pytest

from app.llm.enums import ModelName
from app.llm.schemas import (
    ClassificationResult,
    DocumentCategory,
    ExaminationResult,
)
from app.workflow.nodes.examine import ExamineNode


class TestExamineNode:

    def test_examine_success(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        examination = ExaminationResult(
            is_valid=True,
            confidence=0.95,
            issues=[],
            summary="The extracted information is valid.",
        )

        structured_model.invoke.return_value = examination

        node = ExamineNode(
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
                reasoning="Contractual terms are present.",
            ),
            "extracted_facts": [
                {
                    "field": "party_a",
                    "value": "ABC Ltd",
                    "confidence": 0.95,
                },
                {
                    "field": "party_b",
                    "value": "XYZ Ltd",
                    "confidence": 0.92,
                },
            ],
            "examination": None,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["examination"] == examination
        assert result["examination"].is_valid is True
        assert result["examination"].confidence == 0.95
        assert result["examination"].issues == []
        assert result["error"] is None

    def test_examine_uses_model_factory(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExaminationResult(
            is_valid=True,
            confidence=0.90,
            issues=[],
            summary="Valid.",
        )

        node = ExamineNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Some document"}],
            "classification": None,
            "extracted_facts": [],
            "error": None,
        }

        # Act
        node(state)

        # Assert
        model_factory.create_model.assert_called_once_with(
            ModelName.GEMINI_2_5_FLASH,
        )

    def test_examine_uses_structured_output(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExaminationResult(
            is_valid=True,
            confidence=0.90,
            issues=[],
            summary="Valid.",
        )

        node = ExamineNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Some document"}],
            "classification": None,
            "extracted_facts": [],
            "error": None,
        }

        # Act
        node(state)

        # Assert
        model.with_structured_output.assert_called_once_with(
            ExaminationResult,
        )

    def test_examine_prompt_contains_document_and_facts(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExaminationResult(
            is_valid=True,
            confidence=0.90,
            issues=[],
            summary="Valid.",
        )

        node = ExamineNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [
                {
                    "text": "ABC Ltd signed the agreement."
                }
            ],
            "classification": ClassificationResult(
                document_type=DocumentCategory.CONTRACT,
                confidence=0.95,
                reasoning="Contract.",
            ),
            "extracted_facts": [
                {
                    "field": "party_a",
                    "value": "ABC Ltd",
                    "confidence": 0.95,
                }
            ],
            "error": None,
        }

        # Act
        node(state)

        # Assert
        prompt = structured_model.invoke.call_args.args[0]

        assert "contract" in prompt
        assert "ABC Ltd signed the agreement." in prompt
        assert "party_a" in prompt
        assert "ABC Ltd" in prompt

    def test_examine_handles_empty_facts(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExaminationResult(
            is_valid=False,
            confidence=0.40,
            issues=["No extracted facts were available."],
            summary="Unable to validate the document.",
        )

        node = ExamineNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Some document"}],
            "classification": None,
            "extracted_facts": [],
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["examination"].is_valid is False
        assert len(result["examination"].issues) == 1
        assert result["error"] is None

    def test_examine_converts_model_exception_to_error_state(self):
        # Arrange
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.side_effect = RuntimeError(
            "LLM unavailable"
        )

        node = ExamineNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Some document"}],
            "extracted_facts": [],
            "retry_count": 0,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["error"] == "LLM unavailable"
        assert result["retry_count"] == 1