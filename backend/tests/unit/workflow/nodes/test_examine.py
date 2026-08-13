from unittest.mock import MagicMock

import pytest

from app.llm.enums import ModelName
from app.llm.schemas import ExaminationResult
from app.workflow.nodes.examine import ExamineNode


class TestExamineNode:

    def test_examine_success(self):
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExaminationResult(
            is_valid=True,
            confidence=0.95,
            issues=[],
            summary="The extracted information is consistent.",
        )

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
            "extracted_facts": [
                {
                    "field": "party_a",
                    "value": "ABC Ltd",
                    "confidence": 0.95,
                }
            ],
            "error": None,
        }

        result = node(state)

        assert result["examination"]["is_valid"] is True
        assert result["examination"]["confidence"] == 0.95
        assert result["examination"]["issues"] == []
        assert result["error"] is None

    def test_examine_uses_model_factory(self):
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
            "documents": [{"text": "Document"}],
            "extracted_facts": [],
            "error": None,
        }

        node(state)

        model_factory.create_model.assert_called_once_with(
            ModelName.GEMINI_2_5_FLASH,
        )

    def test_examine_uses_structured_output(self):
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
            "documents": [{"text": "Document"}],
            "extracted_facts": [],
            "error": None,
        }

        node(state)

        model.with_structured_output.assert_called_once_with(
            ExaminationResult,
        )

    def test_examine_prompt_contains_document_and_facts(self):
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
            "extracted_facts": [
                {
                    "field": "party_a",
                    "value": "ABC Ltd",
                    "confidence": 0.95,
                }
            ],
            "error": None,
        }

        node(state)

        prompt = structured_model.invoke.call_args.args[0]

        assert "ABC Ltd signed the agreement." in prompt
        assert "party_a" in prompt
        assert "ABC Ltd" in prompt

    def test_examine_can_return_invalid_result(self):
        model_factory = MagicMock()
        model = MagicMock()
        structured_model = MagicMock()

        model_factory.create_model.return_value = model
        model.with_structured_output.return_value = structured_model

        structured_model.invoke.return_value = ExaminationResult(
            is_valid=False,
            confidence=0.40,
            issues=["Party name could not be verified."],
            summary="The extracted information requires correction.",
        )

        node = ExamineNode(
            model_factory=model_factory,
            model_name=ModelName.GEMINI_2_5_FLASH,
        )

        state = {
            "documents": [{"text": "Document"}],
            "extracted_facts": [],
            "error": None,
        }

        result = node(state)

        assert result["examination"]["is_valid"] is False
        assert result["examination"]["issues"] == [
            "Party name could not be verified."
        ]

    def test_examine_propagates_model_exception(self):
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
            "documents": [{"text": "Document"}],
            "extracted_facts": [],
            "error": None,
        }

        with pytest.raises(
            RuntimeError,
            match="LLM unavailable",
        ):
            node(state)