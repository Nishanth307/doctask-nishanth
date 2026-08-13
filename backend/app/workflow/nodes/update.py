from app.workflow.state import WorkflowState


class UpdateNode:
    """
    Finalizes the workflow state after examination.
    """

    def __call__(self, state: WorkflowState) -> WorkflowState:
        examination = state.get("examination")

        if examination is None:
            return {
                **state,
                "status": "failed",
                "error": "Examination result is missing",
            }

        updates = {
            "status": "completed",
            "examination_valid": examination.is_valid,
            "examination_confidence": examination.confidence,
            "issues": examination.issues,
            "summary": examination.summary,
        }

        return {
            **state,
            "updates": updates,
            "status": "completed",
            "error": None,
        }