from app.workflow.state import WorkflowState


class ReconcileNode:
    """
    Determines whether extracted information requires human review.
    """

    def __call__(self, state: WorkflowState) -> WorkflowState:
        facts = state.get("extracted_facts", [])

        human_review_required = any(
            fact.get("confidence", 0.0) < 0.80
            for fact in facts
        )

        return {
            **state,
            "human_review_required": human_review_required,
            "error": None,
        }