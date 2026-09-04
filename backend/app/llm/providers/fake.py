"""Mock / Fake models for testing without live API keys."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult, ChatGeneration


class FakeStructuredModel:
    def __init__(self, schema: Any) -> None:
        self.schema = schema

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        schema_name = getattr(self.schema, "__name__", str(self.schema))
        if schema_name == "ClassificationResult":
            from app.llm.schemas import DocumentCategory
            return self.schema(
                document_type=DocumentCategory.CONTRACT,
                confidence=0.95,
                reasoning="Mocked document classification.",
            )
        elif schema_name == "ExtractionResult":
            from app.llm.schemas import ExtractedFact
            return self.schema(
                facts=[
                    ExtractedFact(field="party_a", value="Mock ABC Ltd", confidence=0.85),
                    ExtractedFact(field="party_b", value="Mock XYZ Ltd", confidence=0.55),
                ]
            )
        elif schema_name == "ExaminationResult":
            return self.schema(
                is_valid=True,
                confidence=0.95,
                issues=[],
                summary="Mocked examination is consistent.",
            )
        elif schema_name == "SuggestedChangesResult":
            return self.schema(proposals=[])
        return None


class FakeChatModel(BaseChatModel):
    """LangChain-compatible fake chat model for testing."""

    model_name: str = "fake-model"

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        from langchain_core.messages import AIMessage
        ai_msg = AIMessage(
            content="Mocked response",
            response_metadata={"token_usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25}},
        )
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        return FakeStructuredModel(schema)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        mock = MagicMock()
        mock.content = "Mocked LLM response"
        mock.response_metadata = {"token_usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25}}
        return mock
