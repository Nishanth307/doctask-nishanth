from pathlib import Path

from app.ingestion.loaders.base import DocumentLoader
from app.ingestion.loaders.docx import DocxLoader
from app.ingestion.loaders.pdf import PdfLoader
from app.ingestion.loaders.txt import TxtLoader
from app.ingestion.loaders.types import DocumentFormat


class DocumentLoaderFactory:
    def __init__(self) -> None:
        self._loader_menu: dict[
            DocumentFormat,
            type[DocumentLoader],
        ] = {
            DocumentFormat.PDF: PdfLoader,
            DocumentFormat.DOCX: DocxLoader,
            DocumentFormat.TXT: TxtLoader,
        }

    def create(self, file_path: Path) -> DocumentLoader:
        extension = file_path.suffix.lower()

        try:
            document_format = DocumentFormat(extension)
        except ValueError:
            raise ValueError(f"Unsupported document type: {extension}")

        loader_class = self._loader_menu.get(document_format)

        if loader_class is None:
            raise ValueError(f"No loader configured for: {document_format}")

        return loader_class()
