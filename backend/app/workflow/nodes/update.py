from app.persistence.models.workflow_result import WorkflowResult
from app.persistence.repositories.workflow_result import (
    WorkflowResultRepository,
)
from app.workflow.state import WorkflowState


class UpdateNode:
    def __init__(self, repository: WorkflowResultRepository) -> None:
        self.repository = repository

    def __call__(self, state: WorkflowState) -> WorkflowState:
        classification = state.get("classification")
        if classification is not None:
            if hasattr(classification, "model_dump"):
                try:
                    classification = classification.model_dump(mode="json")
                except TypeError:
                    classification = classification.model_dump()
            elif hasattr(classification, "dict"):
                classification = classification.dict()
        else:
            classification = {}

        examination = state.get("examination")
        if examination is not None:
            if hasattr(examination, "model_dump"):
                try:
                    examination = examination.model_dump(mode="json")
                except TypeError:
                    examination = examination.model_dump()
            elif hasattr(examination, "dict"):
                examination = examination.dict()
        else:
            examination = {}

        result = WorkflowResult(
            run_id=state["run_id"],
            status="completed",
            classification=classification,
            extracted_facts=state.get("extracted_facts", []),
            reconciliation={
                "human_review_required": state.get("human_review_required", False),
            },
            examination=examination,
            human_decision=state.get("human_decision"),
        )

        persisted = self.repository.create(result)

        return {
            **state,
            "status": "completed",
            "result_id": persisted.id,
            "error": None,
        }