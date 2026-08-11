from dataclasses import dataclass

from app.ingestion.loaders.base import LoadedDocument
from app.persistence.models.document_chunk import DocumentChunkModel


@dataclass(frozen=True)
class DocumentIngestionResult:
    loaded_document: LoadedDocument
    chunks: list[DocumentChunkModel]