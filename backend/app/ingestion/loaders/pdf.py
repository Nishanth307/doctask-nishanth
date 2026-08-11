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

        for page_number, page in enumerate(
            reader.pages,
            start=1,
        ):
            text = page.extract_text() or ""

            pages.append(
                {
                    "page": page_number,
                    "text": text,
                }
            )

        text = "\n\n".join(page["text"] for page in pages)

        return LoadedDocument(
            text=text,
            source=str(file_path),
            metadata={
                "format": "pdf",
                "pages": len(reader.pages),
                "page_contents": pages,
            },
        )
