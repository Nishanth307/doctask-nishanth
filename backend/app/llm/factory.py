from abc import ABC, abstractmethod
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.core.constants.enums import GeminiModel, LLMProvider
from app.llm.enums import ModelName

class ModelFactory(ABC):
    @abstractmethod
    def create_model(self, model_name: ModelName) -> BaseChatModel:
        pass 

class DefaultModelFactory(ModelFactory):
    def create_model(self, model_name: ModelName) -> BaseChatModel:
        if model_name == ModelName.GEMINI_2_5_FLASH:
            return ChatGoogleGenerativeAI(
                model=GeminiModel.GEMINI_2_5_FLASH.value,
                api_key=settings.GOOGLE_API_KEY,
                temperature=settings.TEMPERATURE,
                max_output_tokens=settings.MAX_OUTPUT_TOKENS,
            )
    
        raise ValueError(
            f"Unsupported model: {model_name}"
        )
