from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import (
    FindingSeverity,
    ReviewDecision,
    RunStatus,
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
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    severity: FindingSeverity
    review_decision: ReviewDecision
    citation: dict[str, Any] | None
    finding_metadata: dict[str, Any] | None
    created_at: datetime


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    version: int
    approved: bool
    created_at: datetime
    updated_at: datetime


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
