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
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class ExtractedFact(BaseModel):
    field: str
    semantic_key: str = ""
    value: str
    confidence: float = Field(ge=0.0, le=1.0)

    source_document: str = ""
    source_text: str = ""


class ExtractionResult(BaseModel):
    facts: list[ExtractedFact]


class ExaminationResult(BaseModel):
    is_valid: bool
    confidence: float = Field(ge=0.0, le=1.0)
    issues: list[str]
    summary: str


class ChangeType(StrEnum):
    REPLACE_TEXT = "REPLACE_TEXT"
    INSERT_TEXT = "INSERT_TEXT"
    DELETE_TEXT = "DELETE_TEXT"
    NO_SAFE_EDIT = "NO_SAFE_EDIT"
    NEEDS_RESOLUTION = "NEEDS_RESOLUTION"


class SuggestedChangeProposal(BaseModel):
    finding_id: str = Field(description="The unique identifier or title/description of the finding")
    change_type: ChangeType = Field(description="The classification of the proposed change")
    source_location: str | None = Field(default=None, description="Section, heading, or paragraph where edit belongs")
    original_text: str | None = Field(default=None, description="Exact substring from the source document to replace")
    proposed_text: str | None = Field(default=None, description="Exact replacement substring conforming to policy")
    reason: str = Field(description="Concise rationale explaining why this edit satisfies the policy")
    rule_reference: str | None = Field(default=None, description="Applicable rule or policy clause title")
    confidence: str = Field(default="high", description="Confidence level: high, medium, or low")
    requires_human_resolution: bool = Field(default=False, description="True if no safe deterministic edit exists or if sources conflict")


class SuggestedChangesResult(BaseModel):
    proposals: list[SuggestedChangeProposal] = Field(default_factory=list)