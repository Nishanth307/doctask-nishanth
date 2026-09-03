from enum import StrEnum


class ModelProvider(StrEnum):
    GEMINI = "gemini"
    OLLAMA = "ollama"

class ModelName(StrEnum):
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"
    GEMINI_2_0_FLASH = "gemini-2.0-flash"
    GEMINI_3_FLASH = "gemini-3.5-flash"
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    OLLAMA_LLAMA = "llama3.2"

    