from app.services.embedding_types import EmbeddingModel
from app.services.embeddings import EmbeddingService

_model_cache = {}


class HuggingFaceEmbeddingService(EmbeddingService):
    def __init__(self, model: EmbeddingModel = EmbeddingModel.MINILM_L6_V2) -> None:
        self.model_name = model.value

    @property
    def _model(self):
        if self.model_name not in _model_cache:
            try:
                import torch
                torch.set_num_threads(1)
                from sentence_transformers import SentenceTransformer
                _model_cache[self.model_name] = SentenceTransformer(self.model_name, device="cpu")
            except Exception as e:
                _model_cache[self.model_name] = None
        return _model_cache[self.model_name]

    def embed_text(self, text: str) -> list[float]:
        try:
            if self._model is not None:
                embedding = self._model.encode(text, normalize_embeddings=True)
                return embedding.tolist()
        except Exception:
            pass
        return [0.0] * 384

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            if self._model is not None:
                embeddings = self._model.encode(texts, normalize_embeddings=True)
                return embeddings.tolist()
        except Exception:
            pass
        return [[0.0] * 384 for _ in texts]

