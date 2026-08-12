from enum import StrEnum


class ModelProvider(StrEnum):
    GEMINI = "gemini"
    OLLAMA = "ollama"

class ModelName(StrEnum):
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    OLLAMA_LLAMA = "llama3.2"
    