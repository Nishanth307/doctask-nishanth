"""Provider registry for resolving LLM provider instances."""
from __future__ import annotations

from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.gemini import GeminiProvider
from app.llm.providers.groq import GroqProvider
from app.llm.providers.openrouter import OpenRouterProvider
from app.llm.providers.ollama import OllamaProvider


_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "openrouter": OpenRouterProvider,
    "ollama": OllamaProvider,
}


def get_provider(provider_name: str) -> BaseLLMProvider:
    """Resolve and return an instantiated LLM provider adapter."""
    normalized = provider_name.strip().lower()
    provider_cls = _PROVIDERS.get(normalized)
    if not provider_cls:
        available = ", ".join(_PROVIDERS.keys())
        raise ValueError(
            f"Unsupported LLM provider: '{provider_name}'. Available providers: {available}"
        )
    return provider_cls()
