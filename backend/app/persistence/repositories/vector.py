from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models.document_chunk import (
    DocumentChunkModel,
)


@dataclass
class VectorSearchResult:
    chunk: DocumentChunkModel
    score: float


class VectorRepository:

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_chunk(
        self,
        document_id: UUID,
        chunk_index: int,
        text: str,
        metadata: dict,
        embedding: list[float],
    ) -> DocumentChunkModel:

        chunk = DocumentChunkModel(
            document_id=document_id,
            chunk_index=chunk_index,
            text=text,
            chunk_metadata=metadata if metadata is not None else {},
            embedding=embedding,
        )

        self.session.add(chunk)
        self.session.flush()

        return chunk

    def similarity_search(
        self,
        embedding: list[float],
        limit: int = 5,
        document_id: UUID | None = None,
    ) -> list[VectorSearchResult]:

        distance = DocumentChunkModel.embedding.cosine_distance(embedding)

        statement = (
            select(
                DocumentChunkModel,
                distance.label("distance"),
            )
            .where(DocumentChunkModel.embedding.is_not(None))
            .order_by(distance)
            .limit(limit)
        )

        if document_id is not None:
            statement = statement.where(DocumentChunkModel.document_id == document_id)

        result = self.session.execute(statement)

        return [
            VectorSearchResult(
                chunk=chunk,
                score=1.0 - float(distance_value),
            )
            for chunk, distance_value in result.all()
        ]
