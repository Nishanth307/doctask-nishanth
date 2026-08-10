from pathlib import Path

import pytest

from app.ingestion.loaders.docx import DocxLoader
from app.ingestion.loaders.factory import DocumentLoaderFactory
from app.ingestion.loaders.pdf import PdfLoader
from app.ingestion.loaders.txt import TxtLoader


class TestDocumentLoaderFactory:

    def setup_method(self):
        self.factory = DocumentLoaderFactory()

    def test_create_pdf_loader(self):
        # Act
        loader = self.factory.create(
            Path("contract.pdf")
        )

        # Assert
        assert isinstance(loader, PdfLoader)

    def test_create_docx_loader(self):
        # Act
        loader = self.factory.create(
            Path("contract.docx")
        )

        # Assert
        assert isinstance(loader, DocxLoader)

    def test_create_txt_loader(self):
        # Act
        loader = self.factory.create(
            Path("notes.txt")
        )

        # Assert
        assert isinstance(loader, TxtLoader)

    def test_factory_is_case_insensitive(self):
        # Act
        loader = self.factory.create(
            Path("contract.PDF")
        )

        # Assert
        assert isinstance(loader, PdfLoader)

    @pytest.mark.parametrize(
        "filename",
        [
            "image.png",
            "spreadsheet.xlsx",
            "archive.zip",
            "program.exe",
        ],
    )
    def test_unsupported_format(self, filename):
        # Act & Assert
        with pytest.raises(
            ValueError,
            match="Unsupported document type",
        ):
            self.factory.create(Path(filename))
