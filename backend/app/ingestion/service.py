from uuid import UUID

from app.ingestion.chunker import TextChunker
from app.persistence.models.document_chunk import DocumentChunkModel
from app.persistence.repositories.vector import VectorRepository
from app.services.embeddings import EmbeddingService


class IngestionService:

    def __init__(
        self,
        chunker: TextChunker,
        embedding_service: EmbeddingService,
        vector_repository: VectorRepository,
    ) -> None:
        self.chunker = chunker
        self.embedding_service = embedding_service
        self.vector_repository = vector_repository

    def ingest(
        self,
        document_id: UUID,
        text: str,
    ) -> list[DocumentChunkModel]:

        chunks = self.chunker.split(text)

        if not chunks:
            return []

        embeddings = (
            self.embedding_service.embed_documents(
                [chunk.text for chunk in chunks]
            )
        )

        if len(embeddings) != len(chunks):
            raise ValueError(
                "Number of embeddings must match "
                "number of chunks"
            )

        created_chunks: list[DocumentChunkModel] = []

        for chunk, embedding in zip(
            chunks,
            embeddings,
            strict=True,
        ):
            created_chunk = (
                self.vector_repository.add_chunk(
                    document_id=document_id,
                    chunk_index=chunk.index,
                    text=chunk.text,
                    metadata={},
                    embedding=embedding,
                )
            )

            created_chunks.append(created_chunk)

        return created_chunks