from enum import StrEnum

from pydantic import BaseModel, Field


class DocumentCategory(StrEnum):
    CONTRACT = "contract"
    POLICY = "policy"
    REPORT = "report"
    INVOICE = "invoice"
    OTHER = "other"

class ClassificationResult(BaseModel):
    document_type: DocumentCategory
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    reasoning: str

class ExtractedFact(BaseModel):
    field: str 
    value: str 
    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

class ExtractionResult(BaseModel):
    facts: list[ExtractedFact]
    