from unittest.mock import patch

import pytest 

from app.core.config import settings
from app.core.constants.enums import GeminiModel
from app.llm.enums import ModelName
from app.llm.factory import DefaultModelFactory 

class TestDefaultModelfactory:

    @patch("app.llm.factory.settings")
    @patch("app.llm.factory.ChatGoogleGenerativeAI")
    def test_create_gemini_model(self, mock_gemini, mock_settings):
        #Arrange 
        mock_settings.GOOGLE_API_KEY = "test-api-key"
        mock_settings.TEMPERATURE = settings.TEMPERATURE
        mock_settings.MAX_OUTPUT_TOKENS = settings.MAX_OUTPUT_TOKENS
        factory = DefaultModelFactory()

        #Act 
        factory.create_model(ModelName.GEMINI_2_5_FLASH)

        #Assert 
        mock_gemini.assert_called_once_with(
            model=GeminiModel.GEMINI_2_5_FLASH.value,
            api_key="test-api-key",
            temperature=settings.TEMPERATURE,
            max_output_tokens=settings.MAX_OUTPUT_TOKENS,
        )
    
    def test_unsupported_model_raises_error(self):
        #Arrange 
        factory = DefaultModelFactory()

        #Act & Assert 
        with pytest.raises(ValueError, match="Unsupported model"):
            factory.create_model("unsupported-model")
            