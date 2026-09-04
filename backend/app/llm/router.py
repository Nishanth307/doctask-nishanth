"""Model Router connecting LangGraph workflow nodes to the generic Cloud LLM Model Pool."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.core.config import settings
from app.core.errors import classify_llm_error, sanitize_error_message
from app.llm.context import set_last_llm_call
from app.llm.enums import ModelName
from app.llm.pool import ModelCapability, ModelPool, get_model_pool
from app.llm.providers.registry import get_provider

logger = logging.getLogger(__name__)


class AllProvidersFailedError(RuntimeError):
    """Raised when all configured LLM models/providers in the pool fail or are unavailable."""

    def __init__(self, provider_attempts: list[dict[str, Any]]) -> None:
        self.provider_attempts = provider_attempts
        attempted_strs = [f"{a.get('provider')}:{a.get('model')}" for a in provider_attempts]
        models_strs = [str(a.get("model")) for a in provider_attempts]
        lines = [
            f"All configured LLM models failed. Attempted: {', '.join(attempted_strs)}",
            f"All configured Gemini models exhausted or unavailable. Attempted models: {', '.join(models_strs)}",
            "Provider attempt details:",
        ]
        for att in provider_attempts:
            provider = att.get("provider", "unknown")
            model = att.get("model", "unknown")
            err_type = att.get("error_type", "UNKNOWN")
            err_msg = sanitize_error_message(att.get("error_message", "No message"))
            lines.append(f"- {provider} ({model}): [{err_type}] {err_msg}")
        super().__init__("\n".join(lines))


def _extract_token_usage(response: Any) -> tuple[int | None, int | None, int | None]:
    """Safely extract input_tokens, output_tokens, and total_tokens from response metadata."""
    if response is None:
        return None, None, None

    # Check LangChain usage_metadata
    usage_metadata = getattr(response, "usage_metadata", None)
    if isinstance(usage_metadata, dict):
        input_t = usage_metadata.get("input_tokens")
        output_t = usage_metadata.get("output_tokens")
        total_t = usage_metadata.get("total_tokens")
        return input_t, output_t, total_t

    # Check response_metadata.token_usage
    resp_metadata = getattr(response, "response_metadata", None)
    if isinstance(resp_metadata, dict):
        token_usage = resp_metadata.get("token_usage")
        if isinstance(token_usage, dict):
            input_t = token_usage.get("prompt_tokens") or token_usage.get("input_tokens")
            output_t = token_usage.get("completion_tokens") or token_usage.get("output_tokens")
            total_t = token_usage.get("total_tokens")
            return input_t, output_t, total_t

    return None, None, None


def _create_underlying_model(model_name: str, provider_name: str) -> Any:
    """Instantiate underlying chat model from the provider adapter."""
    provider = get_provider(provider_name)
    return provider.create_chat_model(model_name)


class PooledStructuredModel:
    """Structured output model routing through the shared ModelPool with capability validation."""

    def __init__(
        self,
        schema: Any,
        model_pool: ModelPool | None = None,
        required_capabilities: set[ModelCapability] | None = None,
        **kwargs: Any,
    ) -> None:
        self.schema = schema
        self.model_pool = model_pool or get_model_pool()
        self.required_capabilities = required_capabilities or {
            ModelCapability.STRUCTURED_OUTPUT
        }
        self.kwargs = kwargs
        self.last_call_metadata: dict[str, Any] | None = None

    def invoke(self, *args: Any, **invoke_kwargs: Any) -> Any:
        eligible_targets = self.model_pool.get_eligible_models(self.required_capabilities)
        if not eligible_targets:
            # Check all pool targets to build informative failure diagnostics
            all_targets = self.model_pool.get_all_targets()
            dummy_attempts = [
                {
                    "provider": t.provider,
                    "model": t.model,
                    "attempt": 1,
                    "fallback_level": t.priority,
                    "status": "failed",
                    "error_type": t.last_error_type or "QUOTA_EXHAUSTED",
                    "error_message": f"Model is currently {t.status.value} (cooldown until {t.unavailable_until})",
                    "retryable": False,
                }
                for t in all_targets
            ]
            raise AllProvidersFailedError(dummy_attempts)

        attempt_records: list[dict[str, Any]] = []
        max_retries_per_model = getattr(settings, "LLM_PROVIDER_MAX_RETRIES", 2)

        for fallback_level, target in enumerate(eligible_targets):
            provider_name = target.provider
            model_name = target.model

            try:
                base_model = _create_underlying_model(model_name, provider_name)
                structured_model = base_model.with_structured_output(self.schema, **self.kwargs)
            except Exception as init_exc:
                latency_ms = 0
                category, retry_same, fallback_next = classify_llm_error(init_exc)
                sanitized_msg = sanitize_error_message(str(init_exc))
                attempt_records.append({
                    "provider": provider_name,
                    "model": model_name,
                    "attempt": 1,
                    "fallback_level": fallback_level,
                    "latency_ms": latency_ms,
                    "status": "failed",
                    "error_type": category.value,
                    "error_message": sanitized_msg,
                    "retryable": False,
                })
                self.model_pool.mark_unavailable(
                    provider_name, model_name, error_type=category.value
                )
                continue

            for attempt_in_model in range(1, max_retries_per_model + 1):
                start_time = time.perf_counter()
                started_at = datetime.now(timezone.utc).isoformat()
                try:
                    result = structured_model.invoke(*args, **invoke_kwargs)
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    completed_at = datetime.now(timezone.utc).isoformat()

                    input_tokens, output_tokens, total_tokens = _extract_token_usage(result)

                    success_record = {
                        "provider": provider_name,
                        "model": model_name,
                        "attempt": attempt_in_model,
                        "fallback_level": fallback_level,
                        "latency_ms": latency_ms,
                        "status": "success",
                        "error_type": None,
                        "error_message": None,
                        "retryable": False,
                    }
                    attempt_records.append(success_record)

                    self.model_pool.mark_success(provider_name, model_name)

                    self.last_call_metadata = {
                        "provider": provider_name,
                        "model": model_name,
                        "pool_position": target.priority,
                        "attempt": attempt_in_model,
                        "fallback_level": fallback_level,
                        "fallback_used": fallback_level > 0,
                        "started_at": started_at,
                        "completed_at": completed_at,
                        "latency_ms": latency_ms,
                        "status": "completed",
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                        "provider_attempts": attempt_records,
                    }

                    set_last_llm_call(self.last_call_metadata)
                    if fallback_level > 0:
                        logger.warning(
                            f"Structured LLM call succeeded on rotated model {provider_name}:{model_name} "
                            f"(fallback_level={fallback_level})"
                        )
                    return result

                except Exception as exc:
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    category, retry_same, fallback_next = classify_llm_error(exc)
                    sanitized_msg = sanitize_error_message(str(exc))

                    attempt_rec = {
                        "provider": provider_name,
                        "model": model_name,
                        "attempt": attempt_in_model,
                        "fallback_level": fallback_level,
                        "latency_ms": latency_ms,
                        "status": "failed",
                        "error_type": category.value,
                        "error_message": sanitized_msg,
                        "retryable": retry_same or fallback_next,
                    }
                    attempt_records.append(attempt_rec)

                    logger.warning(
                        f"Structured LLM failed {provider_name}:{model_name} "
                        f"attempt={attempt_in_model} category={category.value}: {sanitized_msg}"
                    )

                    # Permanent errors (auth, bad prompt, invalid request) -> abort immediately
                    if not fallback_next and not retry_same:
                        raise exc

                    # Retry same model if transient and retries remain
                    if retry_same and attempt_in_model < max_retries_per_model:
                        time.sleep(0.05)
                        continue

                    # Otherwise mark model temporarily unavailable and rotate to next model
                    self.model_pool.mark_unavailable(
                        provider_name, model_name, error_type=category.value
                    )
                    break

        raise AllProvidersFailedError(attempt_records)


class PooledChatModel:
    """Chat model routing through the shared ModelPool with capability filtering and automatic cooldown."""

    def __init__(
        self,
        model_pool: ModelPool | None = None,
        required_capabilities: set[ModelCapability] | None = None,
        preferred_model: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.model_pool = model_pool or get_model_pool()
        self.required_capabilities = required_capabilities or {
            ModelCapability.TEXT_GENERATION
        }
        self.preferred_model = preferred_model
        self.kwargs = kwargs
        self.last_call_metadata: dict[str, Any] | None = None

    def with_structured_output(self, schema: Any, **kwargs: Any) -> PooledStructuredModel:
        return PooledStructuredModel(
            schema=schema,
            model_pool=self.model_pool,
            required_capabilities={ModelCapability.STRUCTURED_OUTPUT},
            **{**self.kwargs, **kwargs},
        )

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        eligible_targets = self.model_pool.get_eligible_models(self.required_capabilities)
        if not eligible_targets:
            all_targets = self.model_pool.get_all_targets()
            dummy_attempts = [
                {
                    "provider": t.provider,
                    "model": t.model,
                    "attempt": 1,
                    "fallback_level": t.priority,
                    "status": "failed",
                    "error_type": t.last_error_type or "QUOTA_EXHAUSTED",
                    "error_message": f"Model is currently {t.status.value} (cooldown until {t.unavailable_until})",
                    "retryable": False,
                }
                for t in all_targets
            ]
            raise AllProvidersFailedError(dummy_attempts)

        attempt_records: list[dict[str, Any]] = []
        max_retries_per_model = getattr(settings, "LLM_PROVIDER_MAX_RETRIES", 2)

        for fallback_level, target in enumerate(eligible_targets):
            provider_name = target.provider
            model_name = target.model

            try:
                model = _create_underlying_model(model_name, provider_name)
            except Exception as init_exc:
                latency_ms = 0
                category, retry_same, fallback_next = classify_llm_error(init_exc)
                sanitized_msg = sanitize_error_message(str(init_exc))
                attempt_records.append({
                    "provider": provider_name,
                    "model": model_name,
                    "attempt": 1,
                    "fallback_level": fallback_level,
                    "latency_ms": latency_ms,
                    "status": "failed",
                    "error_type": category.value,
                    "error_message": sanitized_msg,
                    "retryable": False,
                })
                self.model_pool.mark_unavailable(
                    provider_name, model_name, error_type=category.value
                )
                continue

            for attempt_in_model in range(1, max_retries_per_model + 1):
                start_time = time.perf_counter()
                started_at = datetime.now(timezone.utc).isoformat()
                try:
                    response = model.invoke(*args, **kwargs)
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    completed_at = datetime.now(timezone.utc).isoformat()

                    input_tokens, output_tokens, total_tokens = _extract_token_usage(response)

                    success_record = {
                        "provider": provider_name,
                        "model": model_name,
                        "attempt": attempt_in_model,
                        "fallback_level": fallback_level,
                        "latency_ms": latency_ms,
                        "status": "success",
                        "error_type": None,
                        "error_message": None,
                        "retryable": False,
                    }
                    attempt_records.append(success_record)

                    self.model_pool.mark_success(provider_name, model_name)

                    self.last_call_metadata = {
                        "provider": provider_name,
                        "model": model_name,
                        "pool_position": target.priority,
                        "attempt": attempt_in_model,
                        "fallback_level": fallback_level,
                        "fallback_used": fallback_level > 0,
                        "started_at": started_at,
                        "completed_at": completed_at,
                        "latency_ms": latency_ms,
                        "status": "completed",
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                        "provider_attempts": attempt_records,
                    }

                    set_last_llm_call(self.last_call_metadata)
                    if fallback_level > 0:
                        logger.warning(
                            f"Chat LLM call succeeded on rotated model {provider_name}:{model_name} "
                            f"(fallback_level={fallback_level})"
                        )
                    return response

                except Exception as exc:
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    category, retry_same, fallback_next = classify_llm_error(exc)
                    sanitized_msg = sanitize_error_message(str(exc))

                    attempt_rec = {
                        "provider": provider_name,
                        "model": model_name,
                        "attempt": attempt_in_model,
                        "fallback_level": fallback_level,
                        "latency_ms": latency_ms,
                        "status": "failed",
                        "error_type": category.value,
                        "error_message": sanitized_msg,
                        "retryable": retry_same or fallback_next,
                    }
                    attempt_records.append(attempt_rec)

                    logger.warning(
                        f"Chat LLM invocation failed {provider_name}:{model_name} "
                        f"attempt={attempt_in_model} category={category.value}: {sanitized_msg}"
                    )

                    # Permanent errors (auth, bad format, invalid request) -> stop immediately
                    if not fallback_next and not retry_same:
                        raise exc

                    # Retry same model if transient and retries remain
                    if retry_same and attempt_in_model < max_retries_per_model:
                        time.sleep(0.05)
                        continue

                    # Otherwise mark model temporarily unavailable and rotate to next model
                    self.model_pool.mark_unavailable(
                        provider_name, model_name, error_type=category.value
                    )
                    break

        raise AllProvidersFailedError(attempt_records)

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs: Any) -> ChatResult:
        response = self.invoke(messages, stop=stop, **kwargs)
        generation = ChatGeneration(message=response)
        return ChatResult(generations=[generation])


class ModelRouter:
    """Universal router mapping workflow requests to the generic ModelPool."""

    def __init__(self, model_pool: ModelPool | None = None) -> None:
        self.model_pool = model_pool or get_model_pool()

    def get_model(
        self,
        required_capabilities: set[ModelCapability] | None = None,
        preferred_model: str | None = None,
        **kwargs: Any,
    ) -> PooledChatModel:
        """Get a pooled chat model satisfying required capabilities."""
        return PooledChatModel(
            model_pool=self.model_pool,
            required_capabilities=required_capabilities or {ModelCapability.TEXT_GENERATION},
            preferred_model=preferred_model,
            **kwargs,
        )

    def get_structured_model(
        self,
        schema: Any,
        required_capabilities: set[ModelCapability] | None = None,
        **kwargs: Any,
    ) -> PooledStructuredModel:
        """Get a pooled structured model targeting a Pydantic schema."""
        return PooledStructuredModel(
            schema=schema,
            model_pool=self.model_pool,
            required_capabilities=required_capabilities or {ModelCapability.STRUCTURED_OUTPUT},
            **kwargs,
        )


# Global singleton router
_global_router: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    """Retrieve global ModelRouter instance."""
    global _global_router
    if _global_router is None:
        _global_router = ModelRouter()
    return _global_router
