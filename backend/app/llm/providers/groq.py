"""Groq LLM Provider adapter."""
from __future__ import annotations

import os
from typing import Any
from langchain_core.language_models import BaseChatModel
from langchain_groq import ChatGroq

from app.core.config import settings
from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.fake import FakeChatModel


class GroqProvider(BaseLLMProvider):
    """Adapter for Groq cloud models via langchain-groq."""

    provider_name: str = "groq"

    def create_chat_model(self, model_name: str, **kwargs: Any) -> BaseChatModel:
        api_key = kwargs.get("api_key") or settings.GROQ_API_KEY
        temperature = kwargs.get("temperature", settings.TEMPERATURE)

        if not api_key:
            if os.getenv("PYTEST_CURRENT_TEST") or settings.APP_ENV == "test":
                return FakeChatModel(model_name=model_name)
            raise ValueError("Missing required API key for Groq. Set GROQ_API_KEY.")

        return ChatGroq(
            model_name=model_name,
            api_key=api_key,
            temperature=temperature,
        )
