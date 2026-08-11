from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from app.ingestion.loaders.base import LoadedDocument
from app.ingestion.pipeline import DocumentIngestionPipeline
from app.ingestion.result import DocumentIngestionResult


class TestDocumentIngestionPipeline:

    def setup_method(self):
        self.loader_factory = Mock()
        self.loader = Mock()
        self.ingestion_service = Mock()

        self.pipeline = DocumentIngestionPipeline(
            loader_factory=self.loader_factory,
            ingestion_service=self.ingestion_service,
        )

        self.document_id = uuid4()
        self.file_path = Path("contract.pdf")

    def test_ingest_document(self):
        # Arrange
        loaded_document = LoadedDocument(
            text="Hello DocTask",
            source=str(self.file_path),
            metadata={
                "format": "pdf",
                "pages": 1,
            },
        )

        expected_chunks = [
            Mock(),
            Mock(),
        ]

        self.loader_factory.create.return_value = (
            self.loader
        )

        self.loader.load.return_value = (
            loaded_document
        )

        self.ingestion_service.ingest.return_value = (
            expected_chunks
        )

        # Act
        result = self.pipeline.ingest(
            document_id=self.document_id,
            file_path=self.file_path,
        )

        # Assert
        assert isinstance(result, DocumentIngestionResult)
        assert result.loaded_document == loaded_document
        assert result.chunks == expected_chunks

        self.loader_factory.create.assert_called_once_with(
            self.file_path
        )

        self.loader.load.assert_called_once_with(
            self.file_path
        )

        self.ingestion_service.ingest.assert_called_once_with(
            document_id=self.document_id,
            text="Hello DocTask",
        )

    def test_empty_document_is_passed_to_ingestion_service(self):
        # Arrange
        loaded_document = LoadedDocument(
            text="",
            source=str(self.file_path),
            metadata={
                "format": "pdf",
            },
        )

        self.loader_factory.create.return_value = (
            self.loader
        )

        self.loader.load.return_value = (
            loaded_document
        )

        self.ingestion_service.ingest.return_value = []

        # Act
        result = self.pipeline.ingest(
            document_id=self.document_id,
            file_path=self.file_path,
        )

        # Assert
        assert isinstance(result, DocumentIngestionResult)
        assert result.loaded_document.text == ""
        assert result.chunks == []

        self.ingestion_service.ingest.assert_called_once_with(
            document_id=self.document_id,
            text="",
        )