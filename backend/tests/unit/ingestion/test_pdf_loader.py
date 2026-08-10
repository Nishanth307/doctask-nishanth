from pathlib import Path
from unittest.mock import MagicMock, patch

from app.ingestion.loaders.pdf import PdfLoader


class TestPdfLoader:

    @patch("app.ingestion.loaders.pdf.PdfReader")
    def test_load_pdf(self, mock_pdf_reader):
        # Arrange
        file_path = Path("contract.pdf")
        
        # Mock pages
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Hello DocTask"
        
        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader_instance

        loader = PdfLoader()

        # Act
        result = loader.load(file_path)

        # Assert
        assert "Hello DocTask" in result.text
        assert result.source == str(file_path)
        assert result.metadata["format"] == "pdf"
        assert result.metadata["pages"] == 1
        mock_pdf_reader.assert_called_once_with(str(file_path))

    @patch("app.ingestion.loaders.pdf.PdfReader")
    def test_load_multiple_pages(self, mock_pdf_reader):
        # Arrange
        file_path = Path("multi.pdf")
        
        # Mock multiple pages
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page One"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page Two"
        
        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page1, mock_page2]
        mock_pdf_reader.return_value = mock_reader_instance

        loader = PdfLoader()

        # Act
        result = loader.load(file_path)

        # Assert
        assert "Page One" in result.text
        assert "Page Two" in result.text
        assert result.metadata["pages"] == 2

    @patch("app.ingestion.loaders.pdf.PdfReader")
    def test_load_empty_pdf(self, mock_pdf_reader):
        # Arrange
        file_path = Path("empty.pdf")
        
        # Mock empty page
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        
        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader_instance

        loader = PdfLoader()

        # Act
        result = loader.load(file_path)

        # Assert
        assert result.text == ""
        assert result.metadata["format"] == "pdf"
        assert result.metadata["pages"] == 1