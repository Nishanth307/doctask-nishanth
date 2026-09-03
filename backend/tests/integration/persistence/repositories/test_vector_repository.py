from uuid import uuid4

from app.persistence.models.document import Document
from app.persistence.models.run import Run
from app.persistence.repositories.vector import (
    VectorRepository,
)


def create_vector(
    index: int,
    value: float = 1.0,
) -> list[float]:

    vector = [0.0] * 384
    vector[index] = value

    return vector


class TestVectorRepositoryIntegration:

    def test_similarity_search(
        self,
        db_session,
    ):
        # Arrange
        run_id = uuid4()
        run = Run(
            id=run_id,
            name="Test Run",
        )
        db_session.add(run)
        db_session.flush()

        document_id = uuid4()
        document = Document(
            id=document_id,
            run_id=run_id,
            filename="contract.pdf",
            file_path="contract.pdf",
            file_type=".pdf",
            checksum="somechecksum",
        )
        db_session.add(document)
        db_session.flush()

        repository = VectorRepository(
            db_session
        )

        chunk_a = repository.add_chunk(
            document_id=document_id,
            chunk_index=0,
            text="Machine learning document",
            metadata={
                "page": 1,
            },
            embedding=create_vector(0),
        )

        chunk_b = repository.add_chunk(
            document_id=document_id,
            chunk_index=1,
            text="Database document",
            metadata={
                "page": 2,
            },
            embedding=create_vector(1),
        )

        chunk_c = repository.add_chunk(
            document_id=document_id,
            chunk_index=2,
            text="Networking document",
            metadata={
                "page": 3,
            },
            embedding=create_vector(2),
        )

        db_session.flush()

        query_embedding = create_vector(0)

        # Act
        results = repository.similarity_search(
            embedding=query_embedding,
            limit=3,
        )

        # Assert
        assert len(results) == 3

        assert results[0].chunk.id == chunk_a.id

        assert results[0].chunk.text == (
            "Machine learning document"
        )

        assert results[0].chunk.chunk_metadata == {
            "page": 1,
        }

        assert results[0].score > results[1].score
        assert results[0].score > results[2].score
