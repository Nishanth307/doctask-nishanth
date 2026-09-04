"""Generic Error Classification and Sanitization for DocTask Workflows.

Provides runtime-driven error categorization, secret scrubbing, and retryability
determination across all LangGraph nodes.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    VALIDATION = "VALIDATION"
    CONFIGURATION = "CONFIGURATION"
    DEPENDENCY = "DEPENDENCY"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    NETWORK_ERROR = "NETWORK_ERROR"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    CONTEXT_LENGTH = "CONTEXT_LENGTH"
    STRUCTURED_OUTPUT_ERROR = "STRUCTURED_OUTPUT_ERROR"
    DATABASE = "DATABASE"
    STORAGE = "STORAGE"
    LLM = "LLM"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    UNKNOWN = "UNKNOWN"


# Patterns to identify and redact sensitive credentials
_SECRET_PATTERNS = [
    # Google API keys (AIza...)
    (re.compile(r"AIza[0-9A-Za-z\-_]{20,}"), "[REDACTED_API_KEY]"),
    # OpenAI/Anthropic/generic API keys (sk-...)
    (re.compile(r"sk-[0-9A-Za-z\-_]{20,}"), "[REDACTED_API_KEY]"),
    # Groq API keys (gsk_...)
    (re.compile(r"gsk_[0-9A-Za-z\-_]{20,}"), "[REDACTED_API_KEY]"),
    # Bearer tokens
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE), r"\1[REDACTED_TOKEN]"),
    # URL basic auth passwords (e.g. postgresql://user:password@host)
    (re.compile(r"(://[^:]+:)[^@]+(@)"), r"\1[REDACTED_PASSWORD]\2"),
    # Query param or key-value passwords
    (re.compile(r"(password\s*[:=]\s*['\"]?)[^'\"\s&]+(['\"]?)", re.IGNORECASE), r"\1[REDACTED]\2"),
    (re.compile(r"(api_key\s*[:=]\s*['\"]?)[^'\"\s&]+(['\"]?)", re.IGNORECASE), r"\1[REDACTED]\2"),
    (re.compile(r"(secret\s*[:=]\s*['\"]?)[^'\"\s&]+(['\"]?)", re.IGNORECASE), r"\1[REDACTED]\2"),
]



def sanitize_error_message(message: str | None) -> str:
    """Scrub sensitive API keys, tokens, credentials, and passwords from error messages."""
    if not message:
        return ""

    sanitized = str(message)
    for pattern, replacement in _SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized.strip()


def classify_error(exc: Exception | str) -> tuple[ErrorCategory, bool, str]:
    """Classify any runtime error into a standard category, retryability flag, and sanitized message.

    Returns:
        (category: ErrorCategory, retryable: bool, sanitized_message: str)
    """
    raw_message = str(exc)
    sanitized_message = sanitize_error_message(raw_message)
    type_name = type(exc).__name__ if isinstance(exc, Exception) else ""
    type_module = type(exc).__module__ if isinstance(exc, Exception) else ""
    full_type = f"{type_module}.{type_name}".lower()
    lower_msg = raw_message.lower()

    # 1. Timeout Errors (Transient, Retryable)
    if (
        isinstance(exc, TimeoutError)
        or "timeout" in full_type
        or "timeout" in lower_msg
        or "timed out" in lower_msg
        or "deadline exceeded" in lower_msg
    ):
        return ErrorCategory.TIMEOUT, True, sanitized_message

    # 2. Rate Limit & Quota Errors (Transient, Retryable)
    if (
        "ratelimit" in full_type
        or "quota" in lower_msg
        or "429" in lower_msg
        or "resource exhausted" in lower_msg
        or "rate limit" in lower_msg
        or "too many requests" in lower_msg
    ):
        return ErrorCategory.RATE_LIMIT, True, sanitized_message

    # 3. Database Errors
    if (
        "sqlalchemy" in full_type
        or "psycopg" in full_type
        or "psycopg" in lower_msg
        or "database" in lower_msg
        or "postgres" in lower_msg
        or "operationalerror" in full_type
        or "operationalerror" in lower_msg
        or "interfaceerror" in full_type
    ):
        # Transient DB connection failure vs permanent schema/integrity constraint
        is_transient_db = any(
            token in lower_msg
            for token in (
                "connection refused",
                "connection reset",
                "could not receive data",
                "pool timeout",
                "connection closed",
                "terminating connection",
                "broken pipe",
                "connection to server was lost",
                "lost",
            )
        ) or "operationalerror" in full_type or "operationalerror" in lower_msg
        if is_transient_db and "unique" not in lower_msg and "foreignkey" not in lower_msg:
            return ErrorCategory.DATABASE, True, sanitized_message
        return ErrorCategory.DATABASE, False, sanitized_message

    # 4. LLM Provider Errors
    if (
        "google.genai" in full_type
        or "langchain" in full_type
        or "openai" in full_type
        or "gemini" in lower_msg
        or "anthropic" in lower_msg
        or "llm" in lower_msg
        or "model" in lower_msg
        or any(code in lower_msg for code in ("500 internal server error", "502 bad gateway", "503 service unavailable", "504 gateway timeout"))
    ):
        is_transient_llm = any(
            token in lower_msg
            for token in ("503", "502", "500", "overloaded", "temporary", "service unavailable", "internal server error")
        )
        return ErrorCategory.LLM, is_transient_llm, sanitized_message

    # 5. Storage Errors
    if (
        isinstance(exc, FileNotFoundError)
        or "filenotfound" in full_type
        or "nosuchkey" in lower_msg
        or "blobnotfound" in lower_msg
        or "storage" in lower_msg
        or "directory not found" in lower_msg
    ):
        return ErrorCategory.STORAGE, False, sanitized_message

    # 6. Validation Errors (Permanent)
    if (
        isinstance(exc, (ValueError, TypeError))
        or "validationerror" in full_type
        or "validation" in lower_msg
        or "invalid format" in lower_msg
        or "schema" in lower_msg
        or "cannot be null" in lower_msg
    ):
        return ErrorCategory.VALIDATION, False, sanitized_message

    # 7. Document Processing Errors (Permanent)
    if (
        "pdf" in lower_msg
        or "docx" in lower_msg
        or "corrupt" in lower_msg
        or "unsupported document" in lower_msg
        or "parsing failed" in lower_msg
        or "unreadable" in lower_msg
    ):
        return ErrorCategory.DOCUMENT_PROCESSING, False, sanitized_message

    # 8. Configuration & Authentication Errors (Permanent)
    if (
        "unauthorized" in lower_msg
        or "401" in lower_msg
        or "403" in lower_msg
        or "forbidden" in lower_msg
        or "authentication" in lower_msg
        or "missing api key" in lower_msg
        or "invalid api key" in lower_msg
        or "configuration" in lower_msg
    ):
        return ErrorCategory.CONFIGURATION, False, sanitized_message

    # 9. General Transient Network Errors
    if (
        isinstance(exc, ConnectionError)
        or "connectionerror" in full_type
        or "network" in lower_msg
        or "connection reset" in lower_msg
    ):
        return ErrorCategory.TRANSIENT, True, sanitized_message

    # 10. Dependency Errors
    if "dependency" in lower_msg or "module not found" in lower_msg or "importerror" in full_type:
        return ErrorCategory.DEPENDENCY, False, sanitized_message

    # 11. Fallback Unknown
    return ErrorCategory.UNKNOWN, True, sanitized_message


def classify_llm_error(exc: Exception | str) -> tuple[ErrorCategory, bool, bool]:
    """Classify an LLM provider error.

    Returns:
        (category: ErrorCategory, retry_same_provider: bool, fallback_next_provider: bool)
    """
    raw_message = str(exc)
    type_name = type(exc).__name__ if isinstance(exc, Exception) else ""
    type_module = type(exc).__module__ if isinstance(exc, Exception) else ""
    full_type = f"{type_module}.{type_name}".lower()
    lower_msg = raw_message.lower()

    # 1. Authentication / Permission errors -> DO NOT FALLBACK, DO NOT RETRY
    if (
        "auth" in type_name.lower()
        or any(k in lower_msg for k in ("401", "403", "unauthorized", "forbidden", "invalid api key", "api_key invalid", "authentication", "credentials"))
    ):
        return ErrorCategory.AUTHENTICATION_ERROR, False, False

    # 2. Invalid Request / Bad Prompt / Validation / Format -> DO NOT FALLBACK, DO NOT RETRY
    if (
        isinstance(exc, (ValueError, TypeError))
        or "invalid" in type_name.lower()
        or any(k in lower_msg for k in ("invalid_request", "invalid argument", "bad request", "400", "invalid prompt", "prompt format"))
    ):
        return ErrorCategory.INVALID_REQUEST, False, False

    # 3. Context Length Exceeded -> DO NOT RETRY SAME PROVIDER, DO NOT FALLBACK
    if any(k in lower_msg for k in ("context_length", "context length", "maximum context length", "token limit exceeded")):
        return ErrorCategory.CONTEXT_LENGTH, False, False

    # 4. Quota / Resource Exhausted -> FALLBACK IMMEDIATELY
    if (
        type_name in ("ResourceExhausted", "ResourceExhaustedError")
        or any(k in lower_msg for k in ("quota", "resource exhausted", "resourceexhausted", "insufficient_quota", "exceeded your current quota"))
    ):
        return ErrorCategory.QUOTA_EXHAUSTED, False, True

    # 5. Rate Limit -> FALLBACK
    if "429" in lower_msg or "rate limit" in lower_msg or "ratelimit" in full_type or "too many requests" in lower_msg:
        return ErrorCategory.RATE_LIMIT, False, True

    # 6. Timeout -> Retry same provider first, fallback if continues
    if isinstance(exc, TimeoutError) or "timeout" in full_type or "timeout" in lower_msg or "timed out" in lower_msg or "504" in lower_msg or "deadline exceeded" in lower_msg:
        return ErrorCategory.TIMEOUT, True, True

    # 7. Network / Connection Error -> Retry same provider first, fallback if continues
    if isinstance(exc, ConnectionError) or "connectionerror" in full_type or "connection reset" in lower_msg or "connection refused" in lower_msg or "broken pipe" in lower_msg:
        return ErrorCategory.NETWORK_ERROR, True, True

    # 8. Model Not Found -> Fallback to next provider
    if "404" in lower_msg or "model not found" in lower_msg or "does not exist" in lower_msg or "not found" in lower_msg:
        return ErrorCategory.MODEL_NOT_FOUND, False, True

    # 9. Provider Unavailable / 5xx -> Retry same provider first, fallback if continues
    if type_name == "ServiceUnavailable" or any(k in lower_msg for k in ("500", "502", "503", "service unavailable", "serviceunavailable", "bad gateway", "overloaded", "server error")):
        return ErrorCategory.PROVIDER_UNAVAILABLE, True, True

    # 10. Structured Output Error -> Retry same provider once, fallback if continues
    if "validationerror" in full_type or "outputparserexception" in full_type or "jsondecodeerror" in full_type or "failed to parse" in lower_msg or "structured output" in lower_msg:
        return ErrorCategory.STRUCTURED_OUTPUT_ERROR, True, True

    # Fallback default: Transient unknown LLM error -> Fallback
    return ErrorCategory.UNKNOWN, False, True


