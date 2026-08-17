from app.workflow.conflicts import detect_contradictions
from app.workflow.state import WorkflowState


class ReconcileNode:
    """
    Deterministically reconciles extracted facts.

    It never uses regex and never chooses a winning value.
    """

    def __call__(
        self,
        state: WorkflowState,
    ) -> WorkflowState:

        facts = state.get(
            "extracted_facts",
            [],
        )

        contradictions = detect_contradictions(
            facts
        )

        low_confidence = any(
            fact.get("confidence", 0.0) < 0.80
            for fact in facts
        )

        print("========== RECONCILIATION DEBUG ==========")
        print("EXTRACTED FACTS:")
        for fact in facts:
            print(fact)

        print("CONTRADICTIONS:")
        print(contradictions)

        human_review_required = bool(
            contradictions or low_confidence
        )

        return {
            **state,
            "contradictions": contradictions,
            "human_review_required": human_review_required,
            "error": None,
        }