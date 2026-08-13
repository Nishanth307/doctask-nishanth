from typing import Any
from uuid import UUID

from typing_extensions import TypedDict

from app.llm.schemas import ClassificationResult, ExaminationResult


class WorkflowState(TypedDict, total=False):
    run_id: UUID 
    document_ids: list[UUID]
    documents: list[dict[str,Any]]

    classification: ClassificationResult | None
    extracted_facts: list[dict[str, Any]]
    contradictions: list[dict[str, Any]]
    findings: list[dict[str,Any]]
    updates: list[dict[str,Any]]

    retry_count: int 
    max_retries: int 

    human_review_required: bool
    human_decision: str | None

    error: str | None
    simulate_failure: bool 
    examination: ExaminationResult | None
    status: str | None
    result_id: UUID | None

