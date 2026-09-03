from typing import Any
from uuid import UUID

from typing_extensions import TypedDict

from app.llm.schemas import ClassificationResult, ExaminationResult


class WorkflowState(TypedDict, total=False):
    run_id: UUID
    document_ids: list[UUID]
    documents: list[dict[str, Any]]
    rules: list[dict[str, Any]]

    classification: ClassificationResult | None
    extracted_facts: list[dict[str, Any]]
    contradictions: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    updates: list[dict[str, Any]]

    retry_count: int
    max_retries: int

    human_review_required: bool
    human_decision: str | None

    error: str | None
    simulate_failure: bool
    examination: ExaminationResult | None
    suggested_changes: list[dict[str, Any]]
    status: str | None
    result_id: UUID | None

    # --- Document Lifecycle: Mutation & Final Artifact ---
    # The actual mutated final contract text (distinct from the audit report)
    final_document_text: str | None
    # Serialised ChangeRecord dicts from the mutation engine
    applied_changes: list[dict[str, Any]]
    # Change IDs that were skipped because the reviewer rejected the finding
    rejected_changes: list[str]
    # Section-level before/after SHA-256 hash comparison for unchanged-content proof
    section_hashes: dict[str, Any]
    # Result dict from PostEditValidationEngine
    post_edit_validation: dict[str, Any]

