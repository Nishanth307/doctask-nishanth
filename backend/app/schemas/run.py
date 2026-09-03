from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import (
    ApplicationStatus,
    FindingSeverity,
    ReviewDecision,
    RunStatus,
    ValidationStatus,
    WorkflowStage,
)


class RunCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    is_rules: bool


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: RunStatus
    stage: WorkflowStage
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    error_message: str | None
    documents: list[DocumentSummary] = []
    pending_finding_count: int = 0
    approved_finding_count: int = 0
    rejected_finding_count: int = 0
    parent_id: UUID | None = None


class HumanDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]


class WorkflowRunResponse(BaseModel):
    thread_id: str
    state: dict


class WorkflowEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    stage: WorkflowStage
    status: str
    message: str | None
    duration_ms: int | None
    created_at: datetime


class FindingResponse(BaseModel):
    """Canonical finding response.

    Includes both the detected issue AND the proposed change, so callers
    can display the full "Original → Proposed" diff and track lifecycle status.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    document_id: UUID | None = None
    title: str
    description: str
    severity: FindingSeverity
    review_decision: ReviewDecision
    citation: dict[str, Any] | None = None
    finding_metadata: dict[str, Any] | None = None

    # --- Canonical proposed-edit fields ---
    original_value: str | None = None
    proposed_value: str | None = None
    proposed_edit: str | None = None
    source_location: str | None = None

    # --- Lifecycle tracking ---
    application_status: ApplicationStatus | None = None
    validation_status: ValidationStatus | None = None

    created_at: datetime

    @property
    def change_summary(self) -> str | None:
        if self.proposed_edit:
            return self.proposed_edit
        if self.original_value and self.proposed_value:
            return f"{self.original_value} → {self.proposed_value}"
        return None


class ReportResponse(BaseModel):
    """Report response with both audit content and final document artifact."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    version: int
    approved: bool
    created_at: datetime
    updated_at: datetime

    # --- Final Document Artifact ---
    final_content: str | None = None
    final_file_path: str | None = None
    validation_passed: bool | None = None
    validation_summary: str | None = None
    change_history: list[dict[str, Any]] | None = None
    section_hashes: dict[str, Any] | None = None


class WorkflowResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    classification: dict
    extracted_facts: list
    reconciliation: dict
    examination: dict
    human_decision: str | None
    created_at: datetime
    updated_at: datetime


class RunDetailsResponse(BaseModel):
    run: RunResponse
    findings: list[FindingResponse]
    report: ReportResponse | None
    workflow_events: list[WorkflowEventResponse]
    workflow_result: WorkflowResultResponse | None


class ReviewResponse(BaseModel):
    run_id: UUID
    status: RunStatus
    stage: WorkflowStage
    requires_review: bool
    findings: list[FindingResponse]


class ExportResponse(BaseModel):
    """Structured export of the complete final document lifecycle artifact."""
    run_id: UUID
    run_name: str
    status: RunStatus
    stage: WorkflowStage

    # Final document
    has_final_document: bool
    final_content: str | None = None

    # Summary counts
    total_findings: int
    approved_findings: int
    rejected_findings: int
    applied_changes: int
    failed_changes: int

    # Validation
    validation_passed: bool | None = None
    validation_summary: str | None = None

    # Full provenance
    change_history: list[dict[str, Any]] = []
    section_hashes: dict[str, Any] = {}
    findings: list[FindingResponse] = []
