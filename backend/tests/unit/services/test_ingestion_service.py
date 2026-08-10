from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.ingestion.loaders.base import LoadedDocument
from app.ingestion.loaders.factory import DocumentLoaderFactory
from app.persistence.models.document import Document
from app.persistence.repositories.document import DocumentRepository
from app.services.ingestion import IngestionService


class TestIngestionService:

    def setup_method(self):
        self.document_repository = Mock(
            spec=DocumentRepository
        )

        self.loader_factory = Mock(
            spec=DocumentLoaderFactory
        )

        self.service = IngestionService(
            document_repository=self.document_repository,
            loader_factory=self.loader_factory,
        )

    def test_load_document_successfully(
        self,
        tmp_path: Path,
    ):
        # Arrange
        document_id = uuid4()

        file_path = tmp_path / "contract.txt"
        file_path.write_text(
            "This is a contract.",
            encoding="utf-8",
        )

        document = Document(
            id=document_id,
            filename="contract.txt",
            file_path=str(file_path),
            file_type=".txt",
        )

        loader = Mock()

        expected = LoadedDocument(
            text="This is a contract.",
            source=str(file_path),
            metadata={
                "format": "txt",
            },
        )

        self.document_repository.get_by_id.return_value = document
        self.loader_factory.create.return_value = loader
        loader.load.return_value = expected

        # Act
        result = self.service.load_document(
            document_id
        )

        # Assert
        assert result is expected

        self.document_repository.get_by_id.assert_called_once_with(
            document_id
        )

        self.loader_factory.create.assert_called_once_with(
            file_path
        )

        loader.load.assert_called_once_with(
            file_path
        )

    def test_document_not_found(self):
        # Arrange
        document_id = uuid4()

        self.document_repository.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(
            ValueError,
            match="Document not found",
        ):
            self.service.load_document(
                document_id
            )

        self.loader_factory.create.assert_not_called()

    def test_file_not_found(self):
        # Arrange
        document_id = uuid4()

        document = Document(
            id=document_id,
            filename="missing.txt",
            file_path="/does/not/exist.txt",
            file_type=".txt",
        )

        self.document_repository.get_by_id.return_value = document

        # Act & Assert
        with pytest.raises(
            FileNotFoundError,
            match="Document file not found",
        ):
            self.service.load_document(
                document_id
            )

        self.loader_factory.create.assert_not_called()

    def test_factory_failure(self, tmp_path: Path):
        # Arrange
        document_id = uuid4()

        file_path = tmp_path / "unknown.xyz"
        file_path.write_text(
            "unknown",
            encoding="utf-8",
        )

        document = Document(
            id=document_id,
            filename="unknown.xyz",
            file_path=str(file_path),
            file_type=".xyz",
        )

        self.document_repository.get_by_id.return_value = document

        self.loader_factory.create.side_effect = ValueError(
            "Unsupported document type: .xyz"
        )

        # Act & Assert
        with pytest.raises(
            ValueError,
            match="Unsupported document type",
        ):
            self.service.load_document(
                document_id
            )