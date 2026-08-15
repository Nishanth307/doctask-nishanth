from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants.enums import GeminiModel, LLMProvider


# later change to env variables
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "DOCTask"
    APP_ENV: str = "development"
    DEBUG: bool = True

    CORS_ORIGINS: str = "http://localhost:5173"

    API_V1_PREFIX: str = "/api/v1"

    TEMPERATURE: float = 0
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    MAX_OUTPUT_TOKENS: int = 8192

    DEFAULT_PROVIDER: LLMProvider = LLMProvider.GEMINI
    GOOGLE_API_KEY: str | None = None
    GEMINI_MODEL: GeminiModel = GeminiModel.GEMINI_2_5_FLASH

    DATABASE_URL: str = "postgresql+psycopg://user:1234@localhost:5432/doctask"
    UPLOAD_DIRECTORY: str = "storage/uploads"
    GENERATED_DIRECTORY: str = "storage/generated"

    EMBEDDING_PROVIDER: str = "google"

    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


# 💡 General Temperature Guidelines:
#    - Lower values (0-0.3): More deterministic, consistent responses
#    - Medium values (0.7-1.0): Balanced creativity and consistency
#    - Higher values (1.5-2.0): More creative and varied responses

# Max Tokens Parameter:
#    - The script also demonstrates the max_tokens parameter, which limits response length
#    - Lower limits (50) often result in incomplete, cut-off responses
#    - Higher limits (500) allow for complete, detailed responses
