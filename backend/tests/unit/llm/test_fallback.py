import pytest
from unittest.mock import patch, MagicMock
from app.llm.enums import ModelName
from app.llm.factory import FallbackChatModel, DefaultModelFactory, get_fallback_models_config, is_retryable_llm_error

# Custom retryable and non-retryable exceptions for testing
class ResourceExhausted(Exception):
    pass

class AuthError(Exception):
    pass

class TestModelFallback:

    @patch("app.llm.factory.create_underlying_model")
    @patch("app.llm.factory.get_fallback_models_config")
    def test_primary_model_succeeds(self, mock_get_fallbacks, mock_create):
        mock_get_fallbacks.return_value = [ModelName.GEMINI_2_5_FLASH, ModelName.GEMINI_2_5_PRO]
        primary_mock = MagicMock()
        mock_create.return_value = primary_mock
        
        fallback_model = FallbackChatModel(ModelName.GEMINI_2_5_FLASH)
        fallback_model.invoke("test prompt")
        
        mock_create.assert_called_once_with(ModelName.GEMINI_2_5_FLASH)

    @patch("app.llm.factory.create_underlying_model")
    @patch("app.llm.factory.get_fallback_models_config")
    def test_primary_fails_secondary_succeeds(self, mock_get_fallbacks, mock_create):
        mock_get_fallbacks.return_value = [ModelName.GEMINI_2_5_FLASH, ModelName.GEMINI_2_5_PRO]
        
        primary_mock = MagicMock()
        primary_mock.invoke.side_effect = ResourceExhausted("Resource exhausted 429")
        secondary_mock = MagicMock()
        
        def side_effect(name):
            if name == ModelName.GEMINI_2_5_FLASH:
                return primary_mock
            return secondary_mock
        mock_create.side_effect = side_effect
        
        fallback_model = FallbackChatModel(ModelName.GEMINI_2_5_FLASH)
        fallback_model.invoke("test prompt")
        
        assert mock_create.call_count == 2
        mock_create.assert_any_call(ModelName.GEMINI_2_5_FLASH)
        mock_create.assert_any_call(ModelName.GEMINI_2_5_PRO)

    @patch("app.llm.factory.create_underlying_model")
    @patch("app.llm.factory.get_fallback_models_config")
    def test_all_models_fail(self, mock_get_fallbacks, mock_create):
        mock_get_fallbacks.return_value = [ModelName.GEMINI_2_5_FLASH, ModelName.GEMINI_2_5_PRO]
        
        primary_mock = MagicMock()
        primary_mock.invoke.side_effect = ResourceExhausted("429 resource exhausted")
        secondary_mock = MagicMock()
        secondary_mock.invoke.side_effect = ResourceExhausted("429 quota exceeded")
        
        def side_effect(name):
            if name == ModelName.GEMINI_2_5_FLASH:
                return primary_mock
            return secondary_mock
        mock_create.side_effect = side_effect
        
        fallback_model = FallbackChatModel(ModelName.GEMINI_2_5_FLASH)
        with pytest.raises(RuntimeError) as exc_info:
            fallback_model.invoke("test prompt")
            
        assert "All configured Gemini models exhausted or unavailable" in str(exc_info.value)
        assert mock_create.call_count == 2

    @patch("app.llm.factory.create_underlying_model")
    @patch("app.llm.factory.get_fallback_models_config")
    def test_non_retryable_error_does_not_fallback(self, mock_get_fallbacks, mock_create):
        mock_get_fallbacks.return_value = [ModelName.GEMINI_2_5_FLASH, ModelName.GEMINI_2_5_PRO]
        
        primary_mock = MagicMock()
        primary_mock.invoke.side_effect = ValueError("Invalid prompt format")
        mock_create.return_value = primary_mock
        
        fallback_model = FallbackChatModel(ModelName.GEMINI_2_5_FLASH)
        with pytest.raises(ValueError):
            fallback_model.invoke("test prompt")
            
        mock_create.assert_called_once_with(ModelName.GEMINI_2_5_FLASH)

    @patch("app.llm.factory.create_underlying_model")
    @patch("app.llm.factory.get_fallback_models_config")
    def test_auth_error_does_not_fallback(self, mock_get_fallbacks, mock_create):
        mock_get_fallbacks.return_value = [ModelName.GEMINI_2_5_FLASH, ModelName.GEMINI_2_5_PRO]
        
        primary_mock = MagicMock()
        primary_mock.invoke.side_effect = AuthError("API_KEY invalid or incorrect credentials")
        mock_create.return_value = primary_mock
        
        fallback_model = FallbackChatModel(ModelName.GEMINI_2_5_FLASH)
        with pytest.raises(AuthError):
            fallback_model.invoke("test prompt")
            
        mock_create.assert_called_once_with(ModelName.GEMINI_2_5_FLASH)

    def test_model_order_comes_from_config(self):
        with patch("app.core.config.settings.LLM_FALLBACK_MODELS", "gemini-2.5-pro,gemini-2.0-flash"):
            fallbacks = get_fallback_models_config()
            assert fallbacks == [ModelName.GEMINI_2_5_PRO, ModelName.GEMINI_2_0_FLASH]
