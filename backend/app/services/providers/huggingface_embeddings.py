from app.services.embedding_types import EmbeddingModel
from app.services.embeddings import EmbeddingService

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

_model_cache = {}


class HuggingFaceEmbeddingService(EmbeddingService):
    def __init__(self, model: EmbeddingModel = EmbeddingModel.MINILM_L6_V2) -> None:
        self.model_name = model.value
        try:
            if SentenceTransformer is not None:
                if self.model_name in _model_cache:
                    self.model = _model_cache[self.model_name]
                else:
                    try:
                        self.model = SentenceTransformer(self.model_name, local_files_only=True)
                    except Exception:
                        self.model = SentenceTransformer(self.model_name)
                    _model_cache[self.model_name] = self.model
            else:
                self.model = None
        except Exception:
            self.model = None

    def embed_text(self, text: str) -> list[float]:
        try:
            if self.model is not None:
                embedding = self.model.encode(text, normalize_embeddings=True)
                return embedding.tolist()
        except Exception:
            pass
        return [0.0] * 384

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            if self.model is not None:
                embeddings = self.model.encode(texts, normalize_embeddings=True)
                return embeddings.tolist()
        except Exception:
            pass
        return [[0.0] * 384 for _ in texts]

