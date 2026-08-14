from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.core.constants.enums import GeminiModel
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
                    ExtractedFact(field="party_b", value="Mock XYZ Ltd", confidence=0.55), # Low confidence to trigger review!
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

class ModelFactory(ABC):
    @abstractmethod
    def create_model(self, model_name: ModelName) -> BaseChatModel:
        pass 

class DefaultModelFactory(ModelFactory):
    def create_model(self, model_name: ModelName) -> BaseChatModel:
        if model_name != ModelName.GEMINI_2_5_FLASH:
            raise ValueError(
                f"Unsupported model: {model_name}"
            )

        if not settings.GOOGLE_API_KEY:
            # Fall back to fake model for testing and validation when API key is missing
            return FakeChatModel()

        return ChatGoogleGenerativeAI(
            model=GeminiModel.GEMINI_2_5_FLASH.value,
            api_key=settings.GOOGLE_API_KEY,
            temperature=settings.TEMPERATURE,
            max_output_tokens=settings.MAX_OUTPUT_TOKENS,
        )
