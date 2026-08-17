from app.workflow.conflicts import detect_contradictions
from app.workflow.state import WorkflowState


class ReconcileNode:
    """
    Reconciles extracted facts across source documents.

    Contradictions are detected using semantic_key rather than
    literal field names. No conflicting value is selected automatically.
    """

    def __call__(self, state: WorkflowState) -> WorkflowState:
        facts = state.get("extracted_facts", [])

        contradictions = detect_contradictions(facts)

        low_confidence_facts = [
            fact
            for fact in facts
            if fact.get("confidence", 0.0) < 0.80
        ]

        human_review_required = bool(
            contradictions or low_confidence_facts
        )

        return {
            **state,
            "contradictions": contradictions,
            "human_review_required": human_review_required,
            "error": None,
        }