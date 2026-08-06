from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.core.constants.enums import GeminiModel, LLMProvider


class LLMFactory:
    @staticmethod
    def create_llm():
        """
        Factory method for creating LLM instances based on configuration
        """

        if settings.DEFAULT_PROVIDER == LLMProvider.GEMINI:
            return ChatGoogleGenerativeAI(
                model=GeminiModel.GEMINI_2_5_FLASH.value,
                api_key=settings.GOOGLE_API_KEY,
                temperature=settings.TEMPERATURE,
                max_output_tokens=settings.MAX_OUTPUT_TOKENS,
            )

        raise ValueError(f"Unsupported Provider: {settings.DEFAULT_PROVIDER}")
