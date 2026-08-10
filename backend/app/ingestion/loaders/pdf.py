from pathlib import Path

from pypdf import PdfReader

from app.ingestion.loaders.base import (
    DocumentLoader,
    LoadedDocument,
)


class PdfLoader(DocumentLoader):

    def load(self, file_path: Path) -> LoadedDocument:
        reader = PdfReader(str(file_path))
        pages = []

        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)

        text = "\n\n".join(pages)

        return LoadedDocument(
            text=text,
            source=str(file_path),
            metadata={"format": "pdf", "pages": len(reader.pages)},
        )
