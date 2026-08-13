from typing import Any
from uuid import UUID

from app.persistence.models.workflow_result import WorkflowResult
from app.persistence.repositories.workflow_result import (
    WorkflowResultRepository,
)


class WorkflowResultService:
    def __init__(
        self,
        repository: WorkflowResultRepository,
    ) -> None:
        self.repository = repository

    def create_result(
        self,
        run_id: UUID,
        state: dict[str, Any],
    ) -> WorkflowResult:
        classification = state.get("classification")

        if classification is None:
            classification_data = {}
        elif hasattr(classification, "model_dump"):
            classification_data = classification.model_dump(mode="json")
        else:
            classification_data = classification

        examination = state.get("examination")

        if examination is None:
            examination_data = {}
        elif hasattr(examination, "model_dump"):
            examination_data = examination.model_dump(mode="json")
        else:
            examination_data = examination

        reconciliation = {
            "human_review_required": state.get(
                "human_review_required",
                False,
            ),
        }

        result = WorkflowResult(
            run_id=run_id,
            status=state.get("status", "completed"),
            classification=classification_data,
            extracted_facts=state.get(
                "extracted_facts",
                [],
            ),
            reconciliation=reconciliation,
            examination=examination_data,
            human_decision=state.get("human_decision"),
        )

        return self.repository.create(result)

    def get_result(
        self,
        run_id: UUID,
    ) -> WorkflowResult | None:
        return self.repository.get_by_run_id(run_id)
