import time
from unittest.mock import MagicMock, patch
import pytest

from app.llm.context import clear_last_llm_call, get_last_llm_call
from app.llm.pool import ModelCapability, ModelPool, ModelStatus
from app.llm.router import AllProvidersFailedError, ModelRouter
from app.llm.schemas import ClassificationResult, DocumentCategory


class QuotaExceededError(Exception):
    pass


class ServiceUnavailableError(Exception):
    pass


class AuthError(Exception):
    pass


class TestModelRouter:

    def setup_method(self):
        clear_last_llm_call()

    def teardown_method(self):
        clear_last_llm_call()

    @patch("app.llm.router._create_underlying_model")
    def test_primary_model_succeeds_without_fallback(self, mock_create):
        pool = ModelPool(
            pool_config="gemini:gemini-2.5-flash,groq:llama-3.3-70b-versatile",
            primary_model="gemini-2.5-flash",
        )
        router = ModelRouter(model_pool=pool)

        gemini_mock = MagicMock()
        gemini_mock.invoke.return_value = MagicMock(
            content="Primary output",
            response_metadata={"token_usage": {"total_tokens": 100}},
        )
        mock_create.return_value = gemini_mock

        model = router.get_model()
        res = model.invoke("Test prompt")

        assert res.content == "Primary output"
        mock_create.assert_called_once_with("gemini-2.5-flash", "gemini")

        call_meta = get_last_llm_call()
        assert call_meta["provider"] == "gemini"
        assert call_meta["model"] == "gemini-2.5-flash"
        assert call_meta["pool_position"] == 0
        assert call_meta["fallback_used"] is False

    @patch("app.llm.router._create_underlying_model")
    def test_quota_exhausted_marks_cooldown_and_rotates(self, mock_create):
        pool = ModelPool(
            pool_config="gemini:gemini-2.5-flash,gemini:gemini-2.5-flash-lite,groq:llama-3.3-70b-versatile",
            cooldown_seconds=60,
        )
        router = ModelRouter(model_pool=pool)

        gemini_mock = MagicMock()
        gemini_mock.invoke.side_effect = QuotaExceededError("429 RESOURCE_EXHAUSTED: quota exceeded")

        flash_lite_mock = MagicMock()
        flash_lite_mock.invoke.return_value = MagicMock(
            content="Flash Lite output",
            response_metadata={},
        )

        def side_effect(model_name, provider_name):
            if model_name == "gemini-2.5-flash":
                return gemini_mock
            return flash_lite_mock

        mock_create.side_effect = side_effect

        model = router.get_model()
        res = model.invoke("Test prompt")

        assert res.content == "Flash Lite output"

        # Check primary was marked temporarily unavailable in pool
        primary_status = pool.get_model_status("gemini", "gemini-2.5-flash")
        assert primary_status["status"] == ModelStatus.TEMPORARILY_UNAVAILABLE.value
        assert primary_status["last_error_type"] == "QUOTA_EXHAUSTED"

        # Check call metadata
        call_meta = get_last_llm_call()
        assert call_meta["provider"] == "gemini"
        assert call_meta["model"] == "gemini-2.5-flash-lite"
        assert call_meta["fallback_used"] is True
        assert call_meta["fallback_level"] == 1
        assert len(call_meta["provider_attempts"]) == 2
        assert call_meta["provider_attempts"][0]["status"] == "failed"
        assert call_meta["provider_attempts"][1]["status"] == "success"

    @patch("app.llm.router._create_underlying_model")
    def test_transient_error_retries_before_rotating(self, mock_create):
        pool = ModelPool(pool_config="gemini:gemini-2.5-flash,groq:llama-3.3-70b-versatile")
        router = ModelRouter(model_pool=pool)

        gemini_mock = MagicMock()
        # 1st attempt fails with 503, 2nd attempt succeeds
        gemini_mock.invoke.side_effect = [
            ServiceUnavailableError("503 Service Unavailable"),
            MagicMock(content="Success on retry", response_metadata={}),
        ]
        mock_create.return_value = gemini_mock

        model = router.get_model()
        res = model.invoke("Test prompt")

        assert res.content == "Success on retry"
        assert gemini_mock.invoke.call_count == 2
        mock_create.assert_called_once_with("gemini-2.5-flash", "gemini")

        call_meta = get_last_llm_call()
        assert call_meta["provider"] == "gemini"
        assert call_meta["fallback_used"] is False

    @patch("app.llm.router._create_underlying_model")
    def test_auth_error_aborts_immediately_without_rotation(self, mock_create):
        pool = ModelPool(pool_config="gemini:gemini-2.5-flash,groq:llama-3.3-70b-versatile")
        router = ModelRouter(model_pool=pool)

        gemini_mock = MagicMock()
        gemini_mock.invoke.side_effect = AuthError("401 Unauthorized: Invalid API key")
        mock_create.return_value = gemini_mock

        model = router.get_model()
        with pytest.raises(AuthError):
            model.invoke("Test prompt")

        # Did NOT try Groq
        assert mock_create.call_count == 1
        # Primary is not marked temporarily unavailable for auth errors
        assert pool.get_model_status("gemini", "gemini-2.5-flash")["status"] == ModelStatus.AVAILABLE.value

    @patch("app.llm.router._create_underlying_model")
    def test_all_models_fail_raises_all_providers_failed_error(self, mock_create):
        pool = ModelPool(pool_config="gemini:gemini-2.5-flash,groq:llama-3.3-70b-versatile")
        router = ModelRouter(model_pool=pool)

        fail_mock = MagicMock()
        fail_mock.invoke.side_effect = QuotaExceededError("429 Resource exhausted")
        mock_create.return_value = fail_mock

        model = router.get_model()
        with pytest.raises(AllProvidersFailedError) as exc_info:
            model.invoke("Test prompt")

        err = exc_info.value
        assert len(err.provider_attempts) == 2
        assert pool.get_model_status("gemini", "gemini-2.5-flash")["status"] == ModelStatus.TEMPORARILY_UNAVAILABLE.value
        assert pool.get_model_status("groq", "llama-3.3-70b-versatile")["status"] == ModelStatus.TEMPORARILY_UNAVAILABLE.value

    @patch("app.llm.router._create_underlying_model")
    def test_cooldown_recovery_with_router(self, mock_create):
        pool = ModelPool(
            pool_config="gemini:gemini-2.5-flash,groq:llama-3.3-70b-versatile",
            cooldown_seconds=0.1,
        )
        router = ModelRouter(model_pool=pool)

        primary_mock = MagicMock()
        primary_mock.invoke.side_effect = QuotaExceededError("429 Quota reached")

        groq_mock = MagicMock()
        groq_mock.invoke.return_value = MagicMock(content="Groq fallback", response_metadata={})

        def side_effect(model_name, provider_name):
            if provider_name == "gemini":
                return primary_mock
            return groq_mock

        mock_create.side_effect = side_effect

        # Call 1: Primary fails, Groq succeeds
        model = router.get_model()
        res1 = model.invoke("Prompt 1")
        assert res1.content == "Groq fallback"
        assert pool.get_model_status("gemini", "gemini-2.5-flash")["status"] == ModelStatus.TEMPORARILY_UNAVAILABLE.value

        # Call 2: Within cooldown period -> router skips gemini directly to groq!
        mock_create.reset_mock()
        res2 = model.invoke("Prompt 2")
        assert res2.content == "Groq fallback"
        mock_create.assert_called_once_with("llama-3.3-70b-versatile", "groq")

        # Wait for cooldown to expire
        time.sleep(0.15)

        # Primary recovered! Set primary mock to succeed now
        primary_mock.invoke.side_effect = None
        primary_mock.invoke.return_value = MagicMock(content="Gemini recovered", response_metadata={})
        mock_create.reset_mock()

        # Call 3: Primary model eligible again and selected!
        res3 = model.invoke("Prompt 3")
        assert res3.content == "Gemini recovered"
        mock_create.assert_called_once_with("gemini-2.5-flash", "gemini")
        assert pool.get_model_status("gemini", "gemini-2.5-flash")["status"] == ModelStatus.AVAILABLE.value

    @patch("app.llm.router._create_underlying_model")
    def test_structured_output_with_pool_fallback(self, mock_create):
        pool = ModelPool(pool_config="gemini:gemini-2.5-flash,groq:llama-3.3-70b-versatile")
        router = ModelRouter(model_pool=pool)

        primary_mock = MagicMock()
        primary_structured = MagicMock()
        primary_structured.invoke.side_effect = QuotaExceededError("429 Quota exhausted")
        primary_mock.with_structured_output.return_value = primary_structured

        groq_mock = MagicMock()
        groq_structured = MagicMock()
        groq_structured.invoke.return_value = ClassificationResult(
            document_type=DocumentCategory.POLICY,
            confidence=0.92,
            reasoning="Valid policy format",
        )
        groq_mock.with_structured_output.return_value = groq_structured

        def side_effect(model_name, provider_name):
            if provider_name == "gemini":
                return primary_mock
            return groq_mock

        mock_create.side_effect = side_effect

        model = router.get_structured_model(ClassificationResult)
        result = model.invoke("Classify this policy")

        assert isinstance(result, ClassificationResult)
        assert result.document_type == DocumentCategory.POLICY
        assert result.confidence == 0.92

        call_meta = get_last_llm_call()
        assert call_meta["provider"] == "groq"
        assert call_meta["fallback_used"] is True
