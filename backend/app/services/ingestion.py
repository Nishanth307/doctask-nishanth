from pathlib import Path
from uuid import UUID

from app.ingestion.loaders.base import LoadedDocument
from app.ingestion.loaders.factory import DocumentLoaderFactory
from app.persistence.repositories.document import DocumentRepository


class IngestionService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        loader_factory: DocumentLoaderFactory,
    ) -> None:
        self.document_repository = document_repository
        self.loader_factory = loader_factory

    def load_document(self, document_id: UUID) -> LoadedDocument:
        document = self.document_repository.get_by_id(document_id)

        if document is None:
            raise ValueError("Document not found")

        file_path = Path(document.file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        loader = self.loader_factory.create(file_path)

        return loader.load(file_path)
