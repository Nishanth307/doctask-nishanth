import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch
import pytest

from app.core.config import settings
from app.core.errors import ErrorCategory, classify_llm_error, sanitize_error_message
from app.llm.context import (
    clear_last_llm_call,
    get_last_llm_call,
    set_last_llm_call,
)
from app.llm.pool import get_model_pool
from app.llm.factory import (
    AllProvidersFailedError,
    DefaultModelFactory,
    FallbackChatModel,
    FallbackStructuredModel,
    create_model_for_node,
    get_provider_fallback_chain,
)
from app.llm.schemas import (
    ChangeType,
    ClassificationResult,
    DocumentCategory,
    ExaminationResult,
    ExtractedFact,
    ExtractionResult,
    SuggestedChangeProposal,
    SuggestedChangesResult,
)


# Test mock exceptions
class QuotaExceededError(Exception):
    pass


class ServiceUnavailableError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class InvalidPromptError(Exception):
    pass


class TestMultiProviderFallback:

    def setup_method(self):
        clear_last_llm_call()
        get_model_pool().reset()

    def teardown_method(self):
        clear_last_llm_call()
        get_model_pool().reset()

    # 1. No Ollama in default production fallback chain
    def test_no_ollama_in_production_fallback_chain(self):
        chain = get_provider_fallback_chain("gemini-2.5-flash")
        provider_names = [p.lower() for p, _ in chain]
        assert "ollama" not in provider_names
        for provider, model in chain:
            assert "localhost" not in model.lower()
            assert "11434" not in model.lower()

    # 2. Primary Provider Gemini succeeds without fallback
    @patch("app.llm.factory.create_underlying_model")
    def test_primary_provider_gemini_succeeds(self, mock_create):
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content="Analysis complete", response_metadata={"token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}})
        mock_create.return_value = mock_model

        model = FallbackChatModel(primary_model="gemini-2.5-flash", primary_provider="gemini")
        result = model.invoke("Analyze document")

        assert result.content == "Analysis complete"
        assert mock_create.call_count == 1
        call_info = get_last_llm_call()
        assert call_info is not None
        assert call_info["provider"] == "gemini"
        assert call_info["model"] == "gemini-2.5-flash"
        assert call_info["fallback_used"] is False
        assert call_info["fallback_level"] == 0
        assert call_info["input_tokens"] == 100
        assert call_info["output_tokens"] == 50
        assert call_info["total_tokens"] == 150

    # 3. Quota exhausted on primary falls back to fallback 1 (gemini-flash-lite)
    @patch("app.llm.factory.create_underlying_model")
    def test_quota_exhausted_falls_back_to_gemini_flash_lite(self, mock_create):
        gemini_mock = MagicMock()
        gemini_mock.invoke.side_effect = QuotaExceededError("429 RESOURCE_EXHAUSTED: quota exceeded")

        flash_lite_mock = MagicMock()
        flash_lite_mock.invoke.return_value = MagicMock(content="Flash Lite response", response_metadata={})

        def side_effect(model_name, provider_name="gemini"):
            if model_name == "gemini-2.5-flash":
                return gemini_mock
            return flash_lite_mock

        mock_create.side_effect = side_effect

        model = FallbackChatModel(primary_model="gemini-2.5-flash", primary_provider="gemini")
        result = model.invoke("Analyze document")

        assert result.content == "Flash Lite response"
        call_info = get_last_llm_call()
        assert call_info["provider"] == "gemini"
        assert call_info["model"] == settings.LLM_GEMINI_FALLBACK_MODEL
        assert call_info["fallback_used"] is True
        assert call_info["fallback_level"] == 1
        assert len(call_info["provider_attempts"]) == 2
        assert call_info["provider_attempts"][0]["status"] == "failed"
        assert call_info["provider_attempts"][1]["status"] == "success"

    # 4. Multi-hop fallback: Gemini -> Flash-Lite -> Groq -> OpenRouter
    @patch("app.llm.factory.create_underlying_model")
    def test_multi_hop_fallback_through_openrouter(self, mock_create):
        gemini_mock = MagicMock()
        gemini_mock.invoke.side_effect = QuotaExceededError("429 RESOURCE_EXHAUSTED")

        flash_lite_mock = MagicMock()
        flash_lite_mock.invoke.side_effect = QuotaExceededError("429 RESOURCE_EXHAUSTED lite")

        groq_mock = MagicMock()
        groq_mock.invoke.side_effect = QuotaExceededError("429 rate limit reached for groq")

        openrouter_mock = MagicMock()
        openrouter_mock.invoke.return_value = MagicMock(content="OpenRouter success", response_metadata={"token_usage": {"total_tokens": 42}})

        def side_effect(model_name, provider_name="gemini"):
            if provider_name == "gemini" and model_name == "gemini-2.5-flash":
                return gemini_mock
            elif provider_name == "gemini":
                return flash_lite_mock
            elif provider_name == "groq":
                return groq_mock
            elif provider_name == "openrouter":
                return openrouter_mock
            return MagicMock()

        mock_create.side_effect = side_effect

        model = FallbackChatModel(primary_model="gemini-2.5-flash", primary_provider="gemini")
        result = model.invoke("Test prompt")

        assert result.content == "OpenRouter success"
        call_info = get_last_llm_call()
        assert call_info["provider"] == "openrouter"
        assert call_info["fallback_used"] is True
        assert call_info["fallback_level"] == 3
        assert len(call_info["provider_attempts"]) == 4
        assert call_info["provider_attempts"][0]["status"] == "failed"
        assert call_info["provider_attempts"][1]["status"] == "failed"
        assert call_info["provider_attempts"][2]["status"] == "failed"
        assert call_info["provider_attempts"][3]["status"] == "success"

    # 5. Transient failure retries on same provider first before falling back
    @patch("app.llm.factory.create_underlying_model")
    def test_transient_error_retries_same_provider_first(self, mock_create):
        primary_mock = MagicMock()
        # First call fails with 503 Service Unavailable, second call succeeds
        primary_mock.invoke.side_effect = [
            ServiceUnavailableError("503 Service Unavailable"),
            MagicMock(content="Recovered on retry", response_metadata={}),
        ]
        mock_create.return_value = primary_mock

        model = FallbackChatModel(primary_model="gemini-2.5-flash", primary_provider="gemini")
        result = model.invoke("Test prompt")

        assert result.content == "Recovered on retry"
        # Primary was called twice
        assert primary_mock.invoke.call_count == 2
        # No fallback model was created
        assert mock_create.call_count == 1
        call_info = get_last_llm_call()
        assert call_info["fallback_used"] is False
        assert call_info["fallback_level"] == 0

    # 6. Transient failure exhausted retries triggers fallback to next provider
    @patch("app.llm.factory.create_underlying_model")
    def test_transient_exhaustion_triggers_next_provider(self, mock_create):
        gemini_mock = MagicMock()
        # Always fails with 503
        gemini_mock.invoke.side_effect = ServiceUnavailableError("503 Service Unavailable")

        fallback_mock = MagicMock()
        fallback_mock.invoke.return_value = MagicMock(content="Fallback recovered", response_metadata={})

        def side_effect(model_name, provider_name="gemini"):
            if model_name == "gemini-2.5-flash":
                return gemini_mock
            return fallback_mock

        mock_create.side_effect = side_effect

        model = FallbackChatModel(primary_model="gemini-2.5-flash", primary_provider="gemini")
        result = model.invoke("Test prompt")

        assert result.content == "Fallback recovered"
        # Primary was retried (max_retries attempts)
        assert gemini_mock.invoke.call_count == settings.LLM_PROVIDER_MAX_RETRIES
        call_info = get_last_llm_call()
        assert call_info["fallback_used"] is True
        assert call_info["fallback_level"] == 1

    # 7. Authentication / Invalid API key error aborts immediately (NO fallback)
    @patch("app.llm.factory.create_underlying_model")
    def test_auth_error_aborts_without_fallback(self, mock_create):
        gemini_mock = MagicMock()
        gemini_mock.invoke.side_effect = AuthenticationError("401 Unauthorized: Invalid API key")
        mock_create.return_value = gemini_mock

        model = FallbackChatModel(primary_model="gemini-2.5-flash", primary_provider="gemini")

        with pytest.raises(AuthenticationError):
            model.invoke("Test prompt")

        # Did NOT attempt fallback models
        assert mock_create.call_count == 1
        assert gemini_mock.invoke.call_count == 1

    # 8. All providers fail raises AllProvidersFailedError with itemized details
    @patch("app.llm.factory.create_underlying_model")
    def test_all_providers_fail_raises_all_providers_failed_error(self, mock_create):
        fail_mock = MagicMock()
        fail_mock.invoke.side_effect = QuotaExceededError("429 Resource exhausted")
        mock_create.return_value = fail_mock

        model = FallbackChatModel(primary_model="gemini-2.5-flash", primary_provider="gemini")

        with pytest.raises(AllProvidersFailedError) as exc_info:
            model.invoke("Test prompt")

        err = exc_info.value
        assert "All configured Gemini models exhausted or unavailable" in str(err)
        assert len(err.provider_attempts) >= 4

    # 9. Structured outputs work consistently across fallback chain
    @patch("app.llm.factory.create_underlying_model")
    def test_structured_output_fallback_consistency(self, mock_create):
        # Test ClassificationResult
        primary_mock = MagicMock()
        primary_structured = MagicMock()
        primary_structured.invoke.side_effect = QuotaExceededError("429 Quota reached")
        primary_mock.with_structured_output.return_value = primary_structured

        fallback_mock = MagicMock()
        fallback_structured = MagicMock()
        fallback_structured.invoke.return_value = ClassificationResult(
            document_type=DocumentCategory.CONTRACT,
            confidence=0.95,
            reasoning="Valid contract layout detected",
        )
        fallback_mock.with_structured_output.return_value = fallback_structured

        def side_effect(model_name, provider_name="gemini"):
            if model_name == "gemini-2.5-flash":
                return primary_mock
            return fallback_mock

        mock_create.side_effect = side_effect

        factory = DefaultModelFactory()
        structured_model = factory.create_structured_model(
            ClassificationResult,
            model_name="gemini-2.5-flash",
            provider="gemini",
        )
        result = structured_model.invoke("Classify this document")

        assert isinstance(result, ClassificationResult)
        assert result.document_type == DocumentCategory.CONTRACT
        assert result.confidence == 0.95

    # 10. Structured outputs for ExtractionResult and ExaminationResult
    @patch("app.llm.factory.create_underlying_model")
    def test_all_structured_output_schemas(self, mock_create):
        mock_model = MagicMock()
        mock_create.return_value = mock_model

        factory = DefaultModelFactory()

        # ExtractionResult
        extract_structured = MagicMock()
        extract_structured.invoke.return_value = ExtractionResult(
            facts=[
                ExtractedFact(field="payment_terms", semantic_key="payment_terms", value="Net 30", confidence=0.9),
            ]
        )
        mock_model.with_structured_output.return_value = extract_structured
        extract_model = factory.create_structured_model(ExtractionResult)
        ext_res = extract_model.invoke("Extract facts")
        assert isinstance(ext_res, ExtractionResult)
        assert len(ext_res.facts) == 1

        # ExaminationResult
        examine_structured = MagicMock()
        examine_structured.invoke.return_value = ExaminationResult(
            is_valid=True,
            confidence=0.98,
            issues=[],
            summary="All policies satisfied",
        )
        mock_model.with_structured_output.return_value = examine_structured
        examine_model = factory.create_structured_model(ExaminationResult)
        exam_res = examine_model.invoke("Examine compliance")
        assert isinstance(exam_res, ExaminationResult)
        assert exam_res.is_valid is True

        # SuggestedChangesResult
        suggest_structured = MagicMock()
        suggest_structured.invoke.return_value = SuggestedChangesResult(
            proposals=[
                SuggestedChangeProposal(
                    finding_id="finding_1",
                    change_type=ChangeType.REPLACE_TEXT,
                    source_location="Section 2",
                    original_text="old text",
                    proposed_text="new text",
                    reason="Satisfies policy",
                )
            ],
            summary="Replaced text successfully",
        )
        mock_model.with_structured_output.return_value = suggest_structured
        suggest_model = factory.create_structured_model(SuggestedChangesResult)
        sug_res = suggest_model.invoke("Suggest changes")
        assert isinstance(sug_res, SuggestedChangesResult)
        assert len(sug_res.proposals) == 1

    # 11. Secret redaction in error messages and attempts
    def test_secret_redaction(self):
        groq_leak = "Error calling groq with key gsk_abcdef1234567890abcdef123456: 429 quota"
        gemini_leak = "API key AIzaSyD_abcdef1234567890 invalid"
        bearer_leak = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz"
        pg_leak = "postgresql://user:secret_pass123@db.host.com:5432/doctask"

        assert "gsk_" not in sanitize_error_message(groq_leak)
        assert "[REDACTED_API_KEY]" in sanitize_error_message(groq_leak)

        assert "AIza" not in sanitize_error_message(gemini_leak)
        assert "[REDACTED_API_KEY]" in sanitize_error_message(gemini_leak)

        assert "eyJ" not in sanitize_error_message(bearer_leak)
        assert "[REDACTED_TOKEN]" in sanitize_error_message(bearer_leak)

        assert "secret_pass123" not in sanitize_error_message(pg_leak)
        assert "[REDACTED_PASSWORD]" in sanitize_error_message(pg_leak)

    # 12. Concurrency isolation between parallel threads/tasks
    def test_concurrency_isolation_across_threads(self):
        def worker(thread_id: int):
            set_last_llm_call({
                "provider": f"provider_{thread_id}",
                "model": f"model_{thread_id}",
                "thread_id": thread_id,
            })
            # Verify that each thread only sees its own set value
            call = get_last_llm_call()
            assert call is not None
            assert call["provider"] == f"provider_{thread_id}"
            assert call["thread_id"] == thread_id
            clear_last_llm_call()
            assert get_last_llm_call() is None
            return thread_id

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, i) for i in range(5)]
            results = [f.result() for f in futures]

        assert results == list(range(5))

    # 13. Node-specific model tiering removed - shared pool used
    @patch("app.llm.factory.DefaultModelFactory.create_model")
    def test_create_model_for_node_tiering(self, mock_create):
        mock_create.return_value = MagicMock()

        create_model_for_node("classify")
        mock_create.assert_called_with()

        create_model_for_node("examine")
        mock_create.assert_called_with()

        create_model_for_node("extract")
        mock_create.assert_called_with()

        create_model_for_node("suggested_changes")
        mock_create.assert_called_with()

