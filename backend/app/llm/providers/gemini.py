"""Gemini LLM Provider adapter."""
from __future__ import annotations

import os
from typing import Any
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.fake import FakeChatModel


class GeminiProvider(BaseLLMProvider):
    """Adapter for Google Gemini models via langchain-google-genai."""

    provider_name: str = "gemini"

    def create_chat_model(self, model_name: str, **kwargs: Any) -> BaseChatModel:
        api_key = kwargs.get("api_key") or settings.effective_gemini_api_key
        temperature = kwargs.get("temperature", settings.TEMPERATURE)
        max_output_tokens = kwargs.get("max_output_tokens", settings.MAX_OUTPUT_TOKENS)

        if not api_key:
            if os.getenv("PYTEST_CURRENT_TEST") or settings.APP_ENV == "test":
                return FakeChatModel(model_name=model_name)
            raise ValueError(
                "Missing required API key for Gemini. Set GEMINI_API_KEY or GOOGLE_API_KEY."
            )

        return ChatGoogleGenerativeAI(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
