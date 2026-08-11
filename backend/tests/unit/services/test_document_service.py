from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.ingestion.loaders.base import LoadedDocument
from app.ingestion.result import DocumentIngestionResult
from app.persistence.models.document import Document
from app.persistence.models.run import Run
from app.persistence.repositories.document import DocumentRepository
from app.persistence.repositories.run import RunRepository
from app.services.document_service import DocumentService
from app.storage.storage import StorageService
from app.utils.hashing import calculate_sha256


class TestDocumentService:

    def setup_method(self):
        # Arrange
        self.document_repository = Mock(
            spec=DocumentRepository
        )
        self.run_repository = Mock(
            spec=RunRepository
        )
        self.storage = Mock(
            spec=StorageService
        )
        self.ingestion_pipeline = Mock()

        self.service = DocumentService(
            document_repository=self.document_repository,
            run_repository=self.run_repository,
            storage=self.storage,
            ingestion_pipeline=self.ingestion_pipeline,
        )

        self.run_id = uuid4()

        self.run = Run(
            id=self.run_id,
            name="Contract Review",
        )

    def test_upload_pdf_successfully(self):
        # Arrange
        filename = "contract.pdf"
        content = b"contract content"

        self.run_repository.get_by_id.return_value = self.run
        self.document_repository.get_by_checksum.return_value = None

        self.storage.save.return_value = (
            "uploads/contract.pdf"
        )

        expected_document = Document(
            run_id=self.run_id,
            filename=filename,
            file_path="uploads/contract.pdf",
            file_type=".pdf",
            checksum=calculate_sha256(content),
        )

        self.document_repository.create.return_value = (
            expected_document
        )

        self.ingestion_pipeline.ingest.return_value = (
            DocumentIngestionResult(
                loaded_document=LoadedDocument(
                    text="Extracted document text",
                    source="contract.pdf",
                    metadata={"format": "pdf"},
                ),
                chunks=[],
            )
        )

        # Act
        result = self.service.upload_document(
            run_id=self.run_id,
            filename=filename,
            content=content,
        )

        # Assert
        assert result is expected_document
        assert result.filename == "contract.pdf"
        assert result.file_type == ".pdf"
        assert result.run_id == self.run_id
        assert result.checksum == calculate_sha256(content)
        assert result.extracted_text == "Extracted document text"

        self.run_repository.get_by_id.assert_called_once_with(
            self.run_id
        )

        self.document_repository.get_by_checksum.assert_called_once_with(
            calculate_sha256(content)
        )

        self.storage.save.assert_called_once_with(
            filename,
            content,
        )

        self.document_repository.create.assert_called_once()
        self.ingestion_pipeline.ingest.assert_called_once()

    @pytest.mark.parametrize(
        "filename",
        [
            "contract.pdf",
            "contract.docx",
            "contract.txt",
        ],
    )
    def test_supported_file_types(
        self,
        filename,
    ):
        # Arrange
        content = b"document content"

        self.run_repository.get_by_id.return_value = self.run
        self.document_repository.get_by_checksum.return_value = None

        self.storage.save.return_value = (
            f"uploads/{filename}"
        )

        self.document_repository.create.side_effect = (
            lambda document: document
        )

        self.ingestion_pipeline.ingest.return_value = (
            DocumentIngestionResult(
                loaded_document=LoadedDocument(
                    text="some text",
                    source=filename,
                    metadata={},
                ),
                chunks=[],
            )
        )

        # Act
        result = self.service.upload_document(
            run_id=self.run_id,
            filename=filename,
            content=content,
        )

        # Assert
        assert result.filename == filename
        assert result.file_type in {
            ".pdf",
            ".docx",
            ".txt",
        }
        assert result.extracted_text == "some text"

    @pytest.mark.parametrize(
        "filename",
        [
            "contract.exe",
            "contract.jpg",
            "contract.png",
            "contract.zip",
            "contract.csv",
        ],
    )
    def test_unsupported_file_type(
        self,
        filename,
    ):
        # Arrange
        self.run_repository.get_by_id.return_value = self.run

        # Act & Assert
        with pytest.raises(
            ValueError,
            match="Unsupported file type",
        ):
            self.service.upload_document(
                run_id=self.run_id,
                filename=filename,
                content=b"data",
            )

        self.storage.save.assert_not_called()
        self.document_repository.create.assert_not_called()
        self.ingestion_pipeline.ingest.assert_not_called()

    def test_upload_when_run_does_not_exist(self):
        # Arrange
        self.run_repository.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(
            ValueError,
            match="Run not found",
        ):
            self.service.upload_document(
                run_id=self.run_id,
                filename="contract.pdf",
                content=b"data",
            )

        self.document_repository.get_by_checksum.assert_not_called()
        self.storage.save.assert_not_called()
        self.document_repository.create.assert_not_called()
        self.ingestion_pipeline.ingest.assert_not_called()

    def test_duplicate_document(self):
        # Arrange
        content = b"same document"

        existing_document = Document(
            run_id=self.run_id,
            filename="existing.pdf",
            file_path="uploads/existing.pdf",
            file_type=".pdf",
            checksum=calculate_sha256(content),
        )

        self.run_repository.get_by_id.return_value = self.run
        self.document_repository.get_by_checksum.return_value = (
            existing_document
        )

        # Act & Assert
        with pytest.raises(
            ValueError,
            match="Document already exists",
        ):
            self.service.upload_document(
                run_id=self.run_id,
                filename="new.pdf",
                content=content,
            )

        self.storage.save.assert_not_called()
        self.document_repository.create.assert_not_called()
        self.ingestion_pipeline.ingest.assert_not_called()

    def test_empty_file(self):
        # Arrange
        filename = "empty.txt"
        content = b""

        self.run_repository.get_by_id.return_value = self.run
        self.document_repository.get_by_checksum.return_value = None

        self.storage.save.return_value = (
            "uploads/empty.txt"
        )

        self.document_repository.create.side_effect = (
            lambda document: document
        )

        self.ingestion_pipeline.ingest.return_value = (
            DocumentIngestionResult(
                loaded_document=LoadedDocument(
                    text="",
                    source=filename,
                    metadata={},
                ),
                chunks=[],
            )
        )

        # Act
        result = self.service.upload_document(
            run_id=self.run_id,
            filename=filename,
            content=content,
        )

        # Assert
        assert result.filename == filename
        assert result.checksum == calculate_sha256(b"")
        assert result.extracted_text == ""

    def test_uppercase_extension(self):
        # Arrange
        filename = "CONTRACT.PDF"
        content = b"contract"

        self.run_repository.get_by_id.return_value = self.run
        self.document_repository.get_by_checksum.return_value = None

        self.storage.save.return_value = (
            "uploads/CONTRACT.PDF"
        )

        self.document_repository.create.side_effect = (
            lambda document: document
        )

        self.ingestion_pipeline.ingest.return_value = (
            DocumentIngestionResult(
                loaded_document=LoadedDocument(
                    text="contract",
                    source=filename,
                    metadata={},
                ),
                chunks=[],
            )
        )

        # Act
        result = self.service.upload_document(
            run_id=self.run_id,
            filename=filename,
            content=content,
        )

        # Assert
        assert result.file_type == ".pdf"

    def test_filename_with_spaces(self):
        # Arrange
        filename = "my employment contract.pdf"
        content = b"contract"

        self.run_repository.get_by_id.return_value = self.run
        self.document_repository.get_by_checksum.return_value = None

        self.storage.save.return_value = (
            f"uploads/{filename}"
        )

        self.document_repository.create.side_effect = (
            lambda document: document
        )

        self.ingestion_pipeline.ingest.return_value = (
            DocumentIngestionResult(
                loaded_document=LoadedDocument(
                    text="contract",
                    source=filename,
                    metadata={},
                ),
                chunks=[],
            )
        )

        # Act
        result = self.service.upload_document(
            run_id=self.run_id,
            filename=filename,
            content=content,
        )

        # Assert
        assert result.filename == filename
        assert result.file_type == ".pdf"

    def test_storage_failure(self):
        # Arrange
        content = b"contract"

        self.run_repository.get_by_id.return_value = self.run
        self.document_repository.get_by_checksum.return_value = None

        self.storage.save.side_effect = RuntimeError(
            "Storage unavailable"
        )

        # Act & Assert
        with pytest.raises(
            RuntimeError,
            match="Storage unavailable",
        ):
            self.service.upload_document(
                run_id=self.run_id,
                filename="contract.pdf",
                content=content,
            )

        self.document_repository.create.assert_not_called()
        self.ingestion_pipeline.ingest.assert_not_called()

    def test_repository_failure_when_checking_duplicate(self):
        # Arrange
        content = b"contract"

        self.run_repository.get_by_id.return_value = self.run

        self.document_repository.get_by_checksum.side_effect = (
            RuntimeError("Database unavailable")
        )

        # Act & Assert
        with pytest.raises(
            RuntimeError,
            match="Database unavailable",
        ):
            self.service.upload_document(
                run_id=self.run_id,
                filename="contract.pdf",
                content=content,
            )

        self.storage.save.assert_not_called()
        self.ingestion_pipeline.ingest.assert_not_called()

    def test_repository_failure_when_creating_document(self):
        # Arrange
        content = b"contract"

        self.run_repository.get_by_id.return_value = self.run
        self.document_repository.get_by_checksum.return_value = None

        self.storage.save.return_value = (
            "uploads/contract.pdf"
        )

        self.document_repository.create.side_effect = (
            RuntimeError("Database insert failed")
        )

        # Act & Assert
        with pytest.raises(
            RuntimeError,
            match="Database insert failed",
        ):
            self.service.upload_document(
                run_id=self.run_id,
                filename="contract.pdf",
                content=content,
            )

        self.storage.save.assert_called_once()
        self.ingestion_pipeline.ingest.assert_not_called()