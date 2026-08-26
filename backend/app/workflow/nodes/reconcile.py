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

        facts = state.get("extracted_facts", [])

        print("\n" + "=" * 80)
        print("RECONCILIATION DEBUG")
        print("=" * 80)
        print(f"Total extracted facts: {len(facts)}")

        for index, fact in enumerate(facts, start=1):
            print(f"\nFACT #{index}")
            print(f"  field:           {fact.get('field')}")
            print(f"  semantic_key:    {fact.get('semantic_key')}")
            print(f"  value:           {fact.get('value')}")
            print(f"  source_document: {fact.get('source_document')}")
            print(f"  source_text:     {fact.get('source_text')}")

        contradictions = detect_contradictions(facts)

        print("\n" + f"CONTRADICTIONS FOUND: {len(contradictions)}")

        for index, contradiction in enumerate(contradictions, start=1):
            print(f"\nCONTRADICTION #{index}")
            print(f"  semantic_key: {contradiction.get('semantic_key')}")
            print(f"  field:        {contradiction.get('field')}")

            for value in contradiction.get("values", []):
                print(
                    f"    {value.get('source_document')}: {value.get('value')}"
                )

        print("=" * 80 + "\n")

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