"""OpenRouter LLM Provider adapter."""
from __future__ import annotations

import os
from typing import Any
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.fake import FakeChatModel


class OpenRouterProvider(BaseLLMProvider):
    """Adapter for OpenRouter cloud models via langchain-openai with custom base_url."""

    provider_name: str = "openrouter"

    def create_chat_model(self, model_name: str, **kwargs: Any) -> BaseChatModel:
        api_key = kwargs.get("api_key") or settings.effective_openrouter_api_key
        temperature = kwargs.get("temperature", settings.TEMPERATURE)

        if not api_key:
            if os.getenv("PYTEST_CURRENT_TEST") or settings.APP_ENV == "test":
                return FakeChatModel(model_name=model_name)
            raise ValueError("Missing required API key for OpenRouter. Set OPENROUTER_API_KEY.")

        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://doctask.app",
                "X-Title": "DocTask Document Processing",
            },
            temperature=temperature,
        )
