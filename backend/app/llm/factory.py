from abc import ABC, abstractmethod
from typing import Any
from unittest.mock import MagicMock
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.llm.enums import ModelName

class FakeStructuredModel:
    def __init__(self, schema):
        self.schema = schema

    def invoke(self, *args, **kwargs):
        if self.schema.__name__ == "ClassificationResult":
            from app.llm.schemas import DocumentCategory
            return self.schema(
                document_type=DocumentCategory.CONTRACT,
                confidence=0.95,
                reasoning="Mocked document classification.",
            )
        elif self.schema.__name__ == "ExtractionResult":
            from app.llm.schemas import ExtractedFact
            return self.schema(
                facts=[
                    ExtractedFact(field="party_a", value="Mock ABC Ltd", confidence=0.85),
                    ExtractedFact(field="party_b", value="Mock XYZ Ltd", confidence=0.55),
                ]
            )
        elif self.schema.__name__ == "ExaminationResult":
            return self.schema(
                is_valid=True,
                confidence=0.95,
                issues=[],
                summary="Mocked examination is consistent.",
            )
        return None

class FakeChatModel:
    def with_structured_output(self, schema, **kwargs):
        return FakeStructuredModel(schema)

    def invoke(self, *args, **kwargs):
        return MagicMock()

def create_underlying_model(model_name: ModelName) -> Any:
    if model_name not in (
        ModelName.GEMINI_2_5_FLASH,
        ModelName.GEMINI_2_5_PRO,
        ModelName.GEMINI_2_5_FLASH_LITE,
        ModelName.GEMINI_2_0_FLASH,
    ):
        raise ValueError(f"Unsupported model: {model_name}")

    if not settings.GOOGLE_API_KEY:
        return FakeChatModel()

    return ChatGoogleGenerativeAI(
        model=model_name.value,
        api_key=settings.GOOGLE_API_KEY,
        temperature=settings.TEMPERATURE,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
    )

def get_fallback_models_config() -> list[ModelName]:
    models = []
    for item in settings.LLM_FALLBACK_MODELS.split(","):
        item = item.strip()
        try:
            models.append(ModelName(item))
        except ValueError:
            pass
    return models

def is_retryable_llm_error(exc: Exception) -> bool:
    err_str = str(exc).lower()
    class_name = exc.__class__.__name__
    if class_name in ("ResourceExhausted", "ServiceUnavailable"):
        return True
    if "429" in err_str or "503" in err_str:
        return True
    if "quota" in err_str or "rate limit" in err_str or "resource exhausted" in err_str or "temporarily unavailable" in err_str:
        return True
    status_code = getattr(exc, "status_code", None)
    if status_code in (429, 503):
        return True
    return False

class FallbackStructuredModel:
    def __init__(self, primary_name: ModelName, fallback_names: list[ModelName], schema, **kwargs):
        self.primary_name = primary_name
        self.fallback_names = fallback_names
        self.schema = schema
        self.kwargs = kwargs

    def invoke(self, *args, **invoke_kwargs):
        last_exc = None
        attempted = []
        
        sequence = [self.primary_name] + [m for m in self.fallback_names if m != self.primary_name]
        
        for name in sequence:
            attempted.append(name)
            try:
                model = create_underlying_model(name)
                structured = model.with_structured_output(self.schema, **self.kwargs)
                return structured.invoke(*args, **invoke_kwargs)
            except Exception as e:
                if is_retryable_llm_error(e):
                    from app.core.logging import logger
                    logger.info(f"LLM model={name.value} failed reason=quota")
                    last_exc = e
                    continue
                raise e

        attempted_strs = [m.value for m in attempted]
        raise RuntimeError(
            f"All configured Gemini models exhausted or unavailable. Attempted models: {', '.join(attempted_strs)}"
        )

class FallbackChatModel:
    def __init__(self, primary_model_name: ModelName):
        self.primary_model_name = primary_model_name
        self.primary_model = create_underlying_model(primary_model_name)

    def with_structured_output(self, schema, **kwargs):
        fallback_models = get_fallback_models_config()
        return FallbackStructuredModel(self.primary_model_name, fallback_models, schema, **kwargs)

    def invoke(self, *args, **kwargs):
        last_exc = None
        attempted = []
        fallback_models = get_fallback_models_config()
        sequence = [self.primary_model_name] + [m for m in fallback_models if m != self.primary_model_name]
        
        for name in sequence:
            attempted.append(name)
            try:
                if name == self.primary_model_name:
                    model = self.primary_model
                else:
                    model = create_underlying_model(name)
                return model.invoke(*args, **kwargs)
            except Exception as e:
                if is_retryable_llm_error(e):
                    from app.core.logging import logger
                    logger.info(f"LLM model={name.value} failed reason=quota")
                    last_exc = e
                    continue
                raise e

        attempted_strs = [m.value for m in attempted]
        raise RuntimeError(
            f"All configured Gemini models exhausted or unavailable. Attempted models: {', '.join(attempted_strs)}"
        )

class ModelFactory(ABC):
    @abstractmethod
    def create_model(self, model_name: ModelName) -> BaseChatModel:
        pass

class DefaultModelFactory(ModelFactory):
    def create_model(self, model_name: ModelName) -> BaseChatModel:
        # Validate that model_name is a valid ModelName enum or string
        try:
            m_enum = ModelName(model_name)
        except ValueError:
            raise ValueError(f"Unsupported model: {model_name}")
        return FallbackChatModel(m_enum)
