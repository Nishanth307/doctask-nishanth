from unittest.mock import Mock
from uuid import uuid4

from app.persistence.models.document_chunk import (
    DocumentChunkModel,
)
from app.persistence.repositories.vector import (
    VectorRepository,
)


class TestVectorRepository:

    def setup_method(self):
        self.session = Mock()

        self.repository = VectorRepository(
            self.session
        )

    def test_add_chunk(self):
        # Arrange
        document_id = uuid4()

        # Act
        result = self.repository.add_chunk(
            document_id=document_id,
            chunk_index=0,
            text="Hello world",
            metadata={
                "page": 1,
            },
            embedding=[
                0.1,
                0.2,
                0.3,
            ],
        )

        # Assert
        assert isinstance(
            result,
            DocumentChunkModel,
        )

        assert result.document_id == document_id
        assert result.chunk_index == 0
        assert result.text == "Hello world"
        assert getattr(result, "chunk_metadata", getattr(result, "metadata", None)) == {
            "page": 1,
        }

        assert result.embedding == [
            0.1,
            0.2,
            0.3,
        ]

        self.session.add.assert_called_once_with(
            result
        )

        self.session.flush.assert_called_once()

    def test_similarity_search_executes_query(self):
        # Arrange
        self.session.execute.return_value.all.return_value = []

        # Act
        result = self.repository.similarity_search(
            embedding=[
                0.1,
                0.2,
                0.3,
            ],
            limit=5,
        )

        # Assert
        assert result == []

        self.session.execute.assert_called_once()

    def test_similarity_search_with_document_filter(
        self,
    ):
        # Arrange
        document_id = uuid4()

        self.session.execute.return_value.all.return_value = []

        # Act
        result = self.repository.similarity_search(
            embedding=[
                0.1,
                0.2,
                0.3,
            ],
            limit=3,
            document_id=document_id,
        )

        # Assert
        assert result == []

        self.session.execute.assert_called_once()