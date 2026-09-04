"""Model Pool and capability abstraction for multi-provider cloud LLM fallback."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import logging
import threading
import time
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelCapability(StrEnum):
    """Capabilities supported by models in the pool."""
    TEXT_GENERATION = "TEXT_GENERATION"
    STRUCTURED_OUTPUT = "STRUCTURED_OUTPUT"
    JSON_OUTPUT = "JSON_OUTPUT"
    TOOL_CALLING = "TOOL_CALLING"
    LONG_CONTEXT = "LONG_CONTEXT"


class ModelStatus(StrEnum):
    """Lifecycle status of a model within the pool."""
    AVAILABLE = "AVAILABLE"
    TEMPORARILY_UNAVAILABLE = "TEMPORARILY_UNAVAILABLE"
    DISABLED = "DISABLED"


@dataclass
class ModelTarget:
    """Represents a specific cloud model target within the pool."""
    provider: str
    model: str
    capabilities: set[ModelCapability] = field(default_factory=lambda: {
        ModelCapability.TEXT_GENERATION,
        ModelCapability.STRUCTURED_OUTPUT,
        ModelCapability.JSON_OUTPUT,
        ModelCapability.LONG_CONTEXT,
    })
    priority: int = 0
    status: ModelStatus = ModelStatus.AVAILABLE
    unavailable_until: float | None = None
    last_error_type: str | None = None
    last_error_at: str | None = None
    failure_count: int = 0
    success_count: int = 0

    @property
    def key(self) -> str:
        return f"{self.provider.lower()}:{self.model}"


class ModelPool:
    """Thread-safe generic cloud LLM model pool with temporary cooldown tracking."""

    def __init__(
        self,
        pool_config: str | None = None,
        primary_model: str | None = None,
        cooldown_seconds: float | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self.cooldown_seconds = cooldown_seconds or getattr(settings, "LLM_MODEL_COOLDOWN_SECONDS", 300)
        self.pool_config_str = pool_config or getattr(settings, "LLM_MODEL_POOL", "")
        self.primary_model_str = primary_model or getattr(settings, "LLM_PRIMARY_MODEL", "")
        self._targets: list[ModelTarget] = []
        self._init_pool()

    def _init_pool(self) -> None:
        with self._lock:
            self._targets.clear()
            raw_entries = [e.strip() for e in self.pool_config_str.split(",") if e.strip()]
            seen_keys: set[str] = set()

            # First pass: parse configured pool entries
            parsed_entries: list[tuple[str, str]] = []
            for entry in raw_entries:
                if ":" in entry:
                    p, m = entry.split(":", 1)
                    p_clean, m_clean = p.strip().lower(), m.strip()
                else:
                    p_clean, m_clean = "gemini", entry.strip()

                # Strictly exclude Ollama and local models from production pool
                if p_clean == "ollama" or "localhost" in m_clean.lower() or "11434" in m_clean:
                    logger.warning(f"Ignoring local/ollama model from production model pool: {entry}")
                    continue

                key = f"{p_clean}:{m_clean}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    parsed_entries.append((p_clean, m_clean))

            # Ensure primary model is represented first if configured
            if self.primary_model_str:
                primary_m = self.primary_model_str.strip()
                primary_p = getattr(settings, "LLM_PRIMARY_PROVIDER", "gemini").strip().lower()
                primary_key = f"{primary_p}:{primary_m}"
                if primary_key in seen_keys:
                    # Move primary to front
                    parsed_entries.sort(key=lambda x: 0 if f"{x[0]}:{x[1]}" == primary_key else 1)
                elif primary_p != "ollama" and "localhost" not in primary_m:
                    parsed_entries.insert(0, (primary_p, primary_m))

            for priority, (provider, model) in enumerate(parsed_entries):
                self._targets.append(
                    ModelTarget(
                        provider=provider,
                        model=model,
                        priority=priority,
                    )
                )

    def get_eligible_models(
        self,
        required_capabilities: set[ModelCapability] | None = None,
    ) -> list[ModelTarget]:
        """Return all models currently eligible to handle a request, ordered by priority."""
        with self._lock:
            now = time.time()
            eligible: list[ModelTarget] = []

            for target in self._targets:
                # Check if temporary cooldown expired
                if target.status == ModelStatus.TEMPORARILY_UNAVAILABLE:
                    if target.unavailable_until is not None and now >= target.unavailable_until:
                        logger.info(
                            f"Model {target.key} cooldown expired. Restoring to AVAILABLE status."
                        )
                        target.status = ModelStatus.AVAILABLE
                        target.unavailable_until = None

                if target.status == ModelStatus.AVAILABLE:
                    if required_capabilities:
                        if not required_capabilities.issubset(target.capabilities):
                            continue
                    eligible.append(target)

            return sorted(eligible, key=lambda t: t.priority)

    def mark_unavailable(
        self,
        provider: str,
        model: str,
        error_type: str = "UNKNOWN",
        cooldown_seconds: float | None = None,
        retry_after: float | None = None,
    ) -> None:
        """Mark a model as temporarily unavailable following a quota/rate-limit or persistent failure."""
        with self._lock:
            key = f"{provider.lower()}:{model}"
            for target in self._targets:
                if target.key == key:
                    cooldown = (
                        retry_after
                        if (retry_after is not None and retry_after > 0)
                        else (cooldown_seconds or self.cooldown_seconds)
                    )
                    target.status = ModelStatus.TEMPORARILY_UNAVAILABLE
                    target.unavailable_until = time.time() + cooldown
                    target.last_error_type = error_type
                    target.last_error_at = datetime.now(timezone.utc).isoformat()
                    target.failure_count += 1
                    logger.warning(
                        f"Model {target.key} marked TEMPORARILY_UNAVAILABLE for {cooldown}s "
                        f"(error={error_type}, failure_count={target.failure_count})"
                    )
                    return

    def mark_success(self, provider: str, model: str) -> None:
        """Mark a model as successfully invoked, resetting failure counter and ensuring availability."""
        with self._lock:
            key = f"{provider.lower()}:{model}"
            for target in self._targets:
                if target.key == key:
                    target.status = ModelStatus.AVAILABLE
                    target.unavailable_until = None
                    target.failure_count = 0
                    target.success_count += 1
                    return

    def get_model_status(self, provider: str, model: str) -> dict[str, Any] | None:
        """Inspect status of a specific model target."""
        with self._lock:
            key = f"{provider.lower()}:{model}"
            for target in self._targets:
                if target.key == key:
                    return {
                        "provider": target.provider,
                        "model": target.model,
                        "status": target.status.value,
                        "priority": target.priority,
                        "unavailable_until": target.unavailable_until,
                        "failure_count": target.failure_count,
                        "success_count": target.success_count,
                        "last_error_type": target.last_error_type,
                        "last_error_at": target.last_error_at,
                    }
            return None

    def get_all_targets(self) -> list[ModelTarget]:
        """Return a snapshot list of all targets."""
        with self._lock:
            return list(self._targets)

    def reset(self) -> None:
        """Reset all targets to AVAILABLE and clear cooldowns (useful for tests)."""
        with self._lock:
            for target in self._targets:
                target.status = ModelStatus.AVAILABLE
                target.unavailable_until = None
                target.failure_count = 0
                target.last_error_type = None
                target.last_error_at = None


# Global singleton instance
_global_model_pool: ModelPool | None = None
_pool_init_lock = threading.Lock()


def get_model_pool() -> ModelPool:
    """Retrieve the global thread-safe ModelPool instance."""
    global _global_model_pool
    if _global_model_pool is None:
        with _pool_init_lock:
            if _global_model_pool is None:
                _global_model_pool = ModelPool()
    return _global_model_pool


def reset_global_model_pool(pool: ModelPool | None = None) -> None:
    """Reset or override the global ModelPool instance (for testing)."""
    global _global_model_pool
    with _pool_init_lock:
        if pool is not None:
            _global_model_pool = pool
        elif _global_model_pool is not None:
            _global_model_pool.reset()
