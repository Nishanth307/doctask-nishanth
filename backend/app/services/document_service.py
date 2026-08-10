from uuid import UUID

from app.persistence.models.document import Document
from app.persistence.repositories.document import DocumentRepository
from app.persistence.repositories.run import RunRepository
from app.storage import StorageService
from app.utils.hashing import calculate_sha256


class DocumentService:
    """
    Business logic for document ingestion.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        run_repository: RunRepository,
        storage: StorageService,
    ) -> None:
        self.document_repository = document_repository
        self.run_repository = run_repository
        self.storage = storage

    def upload_document(self, run_id: UUID, filename: str, content: bytes) -> Document:
        run = self.run_repository.get_by_id(run_id)

        if run is None:
            raise ValueError("Run not found")

        extension = self._get_extension(filename)

        if extension not in (".pdf", ".docx", ".txt"):
            raise ValueError(f"Unsupported file type: {extension}")

        checksum = calculate_sha256(content)

        existing = self.document_repository.get_by_checksum(checksum)

        if existing is not None:
            raise ValueError("Document already exists")

        file_path = self.storage.save(filename, content)

        document = Document(
            run_id=run_id,
            filename=filename,
            file_path=file_path,
            file_type=extension,
            checksum=checksum,
        )

        return self.document_repository.create(document)

    @staticmethod
    def _get_extension(filename: str) -> str:
        parts = filename.rsplit(".", 1)
        if len(parts) > 1:
            return "." + parts[-1].lower()
        return ""
