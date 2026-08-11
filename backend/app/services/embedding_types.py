from enum import StrEnum


class EmbeddingProvider(StrEnum):
    HUGGING_FACE = "huggingface"


class EmbeddingModel(StrEnum):
    MINILM_L6_V2 = "sentence-transformers/all-MiniLM-L6-v2"
