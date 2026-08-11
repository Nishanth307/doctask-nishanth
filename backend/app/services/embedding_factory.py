from app.services.embedding_types import EmbeddingProvider
from app.services.embeddings import EmbeddingService
from app.services.providers.huggingface_embeddings import (
    HuggingFaceEmbeddingService,
)


class EmbeddingFactory:

    def __init__(self) -> None:
        self._embedding_menu: dict[
            EmbeddingProvider,
            type[EmbeddingService],
        ] = {
            EmbeddingProvider.HUGGING_FACE: HuggingFaceEmbeddingService,
        }

    def create(self, provider: EmbeddingProvider) -> EmbeddingService:

        embedding_class = self._embedding_menu.get(provider)

        if embedding_class is None:
            raise ValueError(f"Unsupported embedding provider: {provider}")

        return embedding_class()
