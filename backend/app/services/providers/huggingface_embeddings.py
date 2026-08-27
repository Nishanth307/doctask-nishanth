import torch
from sentence_transformers import SentenceTransformer

from app.services.embedding_types import EmbeddingModel
from app.services.embeddings import EmbeddingService

_model_cache = {}


class HuggingFaceEmbeddingService(EmbeddingService):
    def __init__(self, model: EmbeddingModel = EmbeddingModel.MINILM_L6_V2) -> None:
        if model.value not in _model_cache:
            try:
                torch.set_num_threads(1)
            except Exception:
                pass
            _model_cache[model.value] = SentenceTransformer(model.value)
        self._model = _model_cache[model.value]

    def embed_text(self, text: str) -> list[float]:
        try:
            embedding = self._model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception:
            return [0.0] * 384

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            embeddings = self._model.encode(texts, normalize_embeddings=True)
            return embeddings.tolist()
        except Exception:
            return [[0.0] * 384 for _ in texts]

