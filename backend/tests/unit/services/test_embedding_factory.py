from unittest.mock import patch

from app.services.embedding_factory import EmbeddingFactory
from app.services.embedding_types import EmbeddingProvider
from app.services.providers.huggingface_embeddings import (
    HuggingFaceEmbeddingService,
)


class TestEmbeddingFactory:

    @patch(
        "app.services.embedding_factory."
        "HuggingFaceEmbeddingService"
    )
    def test_create_huggingface_service(
        self,
        mock_service,
    ):
        factory = EmbeddingFactory()

        factory.create(
            EmbeddingProvider.HUGGING_FACE
        )

        mock_service.assert_called_once()