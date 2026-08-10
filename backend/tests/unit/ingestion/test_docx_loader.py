from pathlib import Path
from unittest.mock import MagicMock, patch

from app.ingestion.loaders.docx import DocxLoader


class TestDocxLoader:

    @patch("app.ingestion.loaders.docx.Document")
    def test_load_docx(self, mock_document):
        # Arrange
        file_path = Path("contract.docx")
        
        # Mock paragraph
        mock_paragraph = MagicMock()
        mock_paragraph.text = "Hello DocTask"
        
        mock_doc_instance = MagicMock()
        mock_doc_instance.paragraphs = [mock_paragraph]
        mock_document.return_value = mock_doc_instance

        loader = DocxLoader()

        # Act
        result = loader.load(file_path)

        # Assert
        assert "Hello DocTask" in result.text
        assert result.source == str(file_path)
        assert result.metadata["format"] == "docx"
        mock_document.assert_called_once_with(str(file_path))

    @patch("app.ingestion.loaders.docx.Document")
    def test_load_multiple_paragraphs(self, mock_document):
        # Arrange
        file_path = Path("multi.docx")
        
        # Mock multiple paragraphs
        mock_p1 = MagicMock()
        mock_p1.text = "Paragraph One"
        mock_p2 = MagicMock()
        mock_p2.text = "Paragraph Two"
        
        mock_doc_instance = MagicMock()
        mock_doc_instance.paragraphs = [mock_p1, mock_p2]
        mock_document.return_value = mock_doc_instance

        loader = DocxLoader()

        # Act
        result = loader.load(file_path)

        # Assert
        assert "Paragraph One" in result.text
        assert "Paragraph Two" in result.text
        assert result.metadata["format"] == "docx"

    @patch("app.ingestion.loaders.docx.Document")
    def test_load_empty_docx(self, mock_document):
        # Arrange
        file_path = Path("empty.docx")
        
        # Mock empty docx
        mock_doc_instance = MagicMock()
        mock_doc_instance.paragraphs = []
        mock_document.return_value = mock_doc_instance

        loader = DocxLoader()

        # Act
        result = loader.load(file_path)

        # Assert
        assert result.text == ""
        assert result.metadata["format"] == "docx"