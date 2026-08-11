from pathlib import Path
from uuid import UUID

from app.ingestion.loaders.factory import DocumentLoaderFactory
from app.ingestion.result import DocumentIngestionResult
from app.ingestion.service import IngestionService
from app.persistence.models.document_chunk import DocumentChunkModel


class DocumentIngestionPipeline:

    def __init__(
        self,
        loader_factory: DocumentLoaderFactory,
        ingestion_service: IngestionService,
    ) -> None:
        self.loader_factory = loader_factory
        self.ingestion_service = ingestion_service

    def ingest(
        self,
        document_id: UUID,
        file_path: Path,
    ) -> DocumentIngestionResult:

        loader = self.loader_factory.create(file_path)

        loaded_document = loader.load(file_path)

        chunks: list[DocumentChunkModel] = (
            self.ingestion_service.ingest(
                document_id=document_id,
                text=loaded_document.text,
            )
        )

        return DocumentIngestionResult(
            loaded_document=loaded_document,
            chunks=chunks,
        )