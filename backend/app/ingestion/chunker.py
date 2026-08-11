from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str


class TextChunker:
    """
    Splits document text into overlapping chunks.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(
                "chunk_size must be greater than 0"
            )

        if chunk_overlap < 0:
            raise ValueError(
                "chunk_overlap cannot be negative"
            )

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller "
                "than chunk_size"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str) -> list[TextChunk]:
        if not text or not text.strip():
            return []

        text = text.strip()

        chunks: list[TextChunk] = []

        start = 0
        index = 0

        step = self.chunk_size - self.chunk_overlap

        while start < len(text):
            end = start + self.chunk_size

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append(
                    TextChunk(
                        index=index,
                        text=chunk_text,
                    )
                )

                index += 1

            start += step

        return chunks