class FakeEmbeddingService:

    def __init__(self,dimensions: int = 4) -> None:
        self.dimensions = dimensions

    def embed_text(self,text: str) -> list[float]:

        if not text:
            return [0.0] * self.dimensions

        return [float(len(text))] * self.dimensions

    def embed_documents(self,texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]