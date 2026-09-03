from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants.enums import GeminiModel, LLMProvider


# later change to env variables
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(Path(__file__).resolve().parent.parent.parent.parent / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "DOCTask"
    APP_ENV: str = "development"
    DEBUG: bool = False  # Override to True in .env for local dev

    # Comma-separated list of allowed origins.
    # Local: set in .env → CORS_ORIGINS=http://localhost:5173
    # Production: set in Render dashboard → e.g. https://doctask.vercel.app
    CORS_ORIGINS: str = "http://localhost:5173"


    API_V1_PREFIX: str = "/api/v1"

    TEMPERATURE: float = 0
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    MAX_OUTPUT_TOKENS: int = 8192

    DEFAULT_PROVIDER: LLMProvider = LLMProvider.GEMINI
    GOOGLE_API_KEY: str | None = None
    GEMINI_MODEL: GeminiModel = GeminiModel.GEMINI_2_5_FLASH
    LLM_PRIMARY_MODEL: str = "gemini-2.5-flash-lite"

    DATABASE_URL: str = "postgresql+psycopg://user:1234@localhost:5432/doctask"
    UPLOAD_DIRECTORY: str = "storage/uploads"
    GENERATED_DIRECTORY: str = "storage/generated"
    STORAGE_BACKEND: str = "local"  # "local" or "gcs"
    GCS_BUCKET_NAME: str | None = None

    EMBEDDING_PROVIDER: str = "google"

    LOG_LEVEL: str = "INFO"
    DOCTASK_WATCH_FOLDER: str = "storage/watch"
    LLM_FALLBACK_MODELS: str = "gemini-2.5-flash-lite,gemini-3.5-flash,gemini-2.5-flash"

    @property
    def absolute_upload_dir(self) -> Path:
        return get_absolute_path(self.UPLOAD_DIRECTORY)

    @property
    def absolute_generated_dir(self) -> Path:
        return get_absolute_path(self.GENERATED_DIRECTORY)

    @property
    def absolute_watch_dir(self) -> Path:
        return get_absolute_path(self.DOCTASK_WATCH_FOLDER)

def _find_project_root() -> Path:
    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parent.parent.parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path("/app"),
    ]
    for candidate in candidates:
        if candidate.exists() and (
            (candidate / "storage").exists()
            or (candidate / "requirements.txt").exists()
            or (candidate / "backend").exists()
            or candidate == Path("/app")
        ):
            return candidate.resolve()
    return Path.cwd().resolve()

PROJECT_ROOT = _find_project_root()
STORAGE_ROOT = PROJECT_ROOT / "storage"

# Define properties to get absolute paths independent of process cwd
def get_absolute_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        return (PROJECT_ROOT / path).resolve()
    return path.resolve()

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
