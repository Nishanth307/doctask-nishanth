from typing import Any
from uuid import UUID

from typing_extensions import TypedDict

from app.llm.schemas import ClassificationResult, ExaminationResult


class NodeError(TypedDict, total=False):
    node_name: str
    error_type: str
    error_message: str
    error_timestamp: str
    retryable: bool
    attempt: int
    checkpoint_id: str | None
    reason: str | None
    provider: str | None
    model: str | None
    fallback_level: int | None
    fallback_used: bool | None
    provider_attempts: list[dict[str, Any]] | None


class NodeExecutionRecord(TypedDict, total=False):
    node_name: str
    status: str
    attempt: int
    duration_ms: int | None
    error_type: str | None
    error_message: str | None
    retryable: bool | None
    timestamp: str
    provider: str | None
    model: str | None
    fallback_level: int | None
    fallback_used: bool | None
    provider_attempts: list[dict[str, Any]] | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None



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

    # --- Node-level Error Observability & Execution History ---
    execution_history: list[dict[str, Any]]
    last_error: dict[str, Any] | None
    current_node: str | None
    node_attempts: dict[str, int]

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

