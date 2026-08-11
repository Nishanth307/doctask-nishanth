from unittest.mock import Mock, patch
import numpy as np

from app.services.providers.huggingface_embeddings import (
    HuggingFaceEmbeddingService,
)


class TestHuggingFaceEmbeddingService:

    def setup_method(self):
        from app.services.providers.huggingface_embeddings import _model_cache
        _model_cache.clear()

    @patch(
        "app.services.providers."
        "huggingface_embeddings.SentenceTransformer"
    )
    def test_embed_text(
        self,
        mock_model_class,
    ):
        # Arrange
        mock_model = Mock()

        mock_model.encode.return_value = np.array([
            0.1,
            0.2,
            0.3,
        ])

        mock_model_class.return_value = mock_model

        service = HuggingFaceEmbeddingService()

        # Act
        result = service.embed_text(
            "Hello world"
        )

        # Assert
        assert result == [
            0.1,
            0.2,
            0.3,
        ]

        mock_model.encode.assert_called_once_with(
            "Hello world",
            normalize_embeddings=True,
        )

    @patch(
        "app.services.providers."
        "huggingface_embeddings.SentenceTransformer"
    )
    def test_embed_documents(
        self,
        mock_model_class,
    ):
        # Arrange
        mock_model = Mock()

        mock_model.encode.return_value = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ])

        mock_model_class.return_value = mock_model

        service = HuggingFaceEmbeddingService()

        # Act
        result = service.embed_documents(
            ["Hello", "world"]
        )

        # Assert
        assert result == [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ]

        mock_model.encode.assert_called_once_with(
            ["Hello", "world"],
            normalize_embeddings=True,
        )