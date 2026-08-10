from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LoadedDocument:
    text: str
    source: str
    metadata: dict[str, Any]


class DocumentLoader(ABC):
    @abstractmethod
    def load(self, file_path: Path) -> LoadedDocument:
        pass
