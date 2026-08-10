from pathlib import Path

from app.ingestion.loaders.base import (
    DocumentLoader,
    LoadedDocument,
)


class TxtLoader(DocumentLoader):

    def load(self, file_path: Path) -> LoadedDocument:
        text = file_path.read_text(encoding="utf-8")

        return LoadedDocument(
            text=text,
            source=str(file_path),
            metadata={
                "format": "txt",
            },
        )
