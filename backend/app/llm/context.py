"""Thread-safe and async-safe context variable for tracking request-scoped LLM execution metadata."""
from __future__ import annotations

import contextvars
from typing import Any

# Tracks the latest LLM call metadata for the current execution context
_current_llm_call: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "current_llm_call", default=None
)


def set_last_llm_call(metadata: dict[str, Any] | None) -> None:
    """Record metadata for the most recent LLM invocation in this execution context."""
    _current_llm_call.set(metadata)


def get_last_llm_call() -> dict[str, Any] | None:
    """Retrieve metadata for the most recent LLM invocation in this execution context."""
    return _current_llm_call.get()


def clear_last_llm_call() -> None:
    """Reset LLM execution metadata for this context."""
    _current_llm_call.set(None)
