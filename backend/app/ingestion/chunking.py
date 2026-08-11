from dataclasses import dataclass


@dataclass
class DocumentChunk:
    text: str
    chunk_index: int
    source: str
    metadata: dict

    @property
    def page(self) -> int | None:
        return self.metadata.get("page")


# eg:
# DocumentChunk(
#     text="The employee is entitled to 20 days...",
#     chunk_index=3,
#     source="contract.pdf",
#     metadata={
#         "format": "pdf",
#         "page": 4,
#     },
# )
