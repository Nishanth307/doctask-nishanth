from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.ingestion.chunker import TextChunk
from app.ingestion.service import IngestionService


class TestIngestionService:

    def setup_method(self):
        self.chunker = Mock()
        self.embedding_service = Mock()
        self.vector_repository = Mock()

        self.service = IngestionService(
            chunker=self.chunker,
            embedding_service=self.embedding_service,
            vector_repository=self.vector_repository,
        )

        self.document_id = uuid4()

    def test_ingest_empty_document(self):
        # Arrange
        self.chunker.split.return_value = []

        # Act
        result = self.service.ingest(
            document_id=self.document_id,
            text="",
        )

        # Assert
        assert result == []

        self.embedding_service.embed_documents.assert_not_called()
        self.vector_repository.add_chunk.assert_not_called()

    def test_ingest_document(self):
        # Arrange
        chunks = [
            TextChunk(
                index=0,
                text="First chunk",
            ),
            TextChunk(
                index=1,
                text="Second chunk",
            ),
        ]

        embeddings = [
            [0.1, 0.2],
            [0.3, 0.4],
        ]

        created_chunk_1 = Mock()
        created_chunk_2 = Mock()

        self.chunker.split.return_value = chunks

        self.embedding_service.embed_documents.return_value = (
            embeddings
        )

        self.vector_repository.add_chunk.side_effect = [
            created_chunk_1,
            created_chunk_2,
        ]

        # Act
        result = self.service.ingest(
            document_id=self.document_id,
            text="Some document",
        )

        # Assert
        assert result == [
            created_chunk_1,
            created_chunk_2,
        ]

        self.chunker.split.assert_called_once_with(
            "Some document"
        )

        self.embedding_service.embed_documents.assert_called_once_with(
            [
                "First chunk",
                "Second chunk",
            ]
        )

        assert (
            self.vector_repository.add_chunk.call_count
            == 2
        )

        self.vector_repository.add_chunk.assert_any_call(
            document_id=self.document_id,
            chunk_index=0,
            text="First chunk",
            metadata={},
            embedding=[0.1, 0.2],
        )

        self.vector_repository.add_chunk.assert_any_call(
            document_id=self.document_id,
            chunk_index=1,
            text="Second chunk",
            metadata={},
            embedding=[0.3, 0.4],
        )

    def test_embedding_count_must_match_chunk_count(self):
        # Arrange
        chunks = [
            TextChunk(
                index=0,
                text="First chunk",
            ),
            TextChunk(
                index=1,
                text="Second chunk",
            ),
        ]

        self.chunker.split.return_value = chunks

        self.embedding_service.embed_documents.return_value = [
            [0.1, 0.2],
        ]

        # Act & Assert
        with pytest.raises(
            ValueError,
            match="Number of embeddings must match",
        ):
            self.service.ingest(
                document_id=self.document_id,
                text="Some document",
            )

        self.vector_repository.add_chunk.assert_not_called()