from typing import Any
from uuid import UUID 

from typing_extensions import TypedDict 

class WorkflowState(TypedDict, total=False):
    run_id: UUID 
    document_ids: list[UUID]
    classification: dict[str, Any]
    extracted_facts: list[dict[str, Any]]
    contradictions: list[dict[str, Any]]
    findings: list[dict[str,Any]]
    updates: list[dict[str,Any]]
    error: str | None 

    