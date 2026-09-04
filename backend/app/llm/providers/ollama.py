"""Ollama LLM Provider adapter (Local Development / Testing Only)."""
from __future__ import annotations

import os
from typing import Any
from langchain_core.language_models import BaseChatModel

from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.fake import FakeChatModel


class OllamaProvider(BaseLLMProvider):
    """Adapter for local Ollama models. Not used in production fallback chain."""

    provider_name: str = "ollama"

    def create_chat_model(self, model_name: str, **kwargs: Any) -> BaseChatModel:
        if os.getenv("PYTEST_CURRENT_TEST"):
            return FakeChatModel(model_name=model_name)

        try:
            from langchain_community.chat_models import ChatOllama
            base_url = kwargs.get("base_url") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            return ChatOllama(model=model_name, base_url=base_url)
        except Exception:
            return FakeChatModel(model_name=model_name)
