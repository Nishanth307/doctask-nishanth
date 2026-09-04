"""Base interface for LLM providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from langchain_core.language_models import BaseChatModel


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    provider_name: str

    @abstractmethod
    def create_chat_model(self, model_name: str, **kwargs: Any) -> BaseChatModel:
        """Create and return a LangChain-compatible chat model for this provider."""
        pass
