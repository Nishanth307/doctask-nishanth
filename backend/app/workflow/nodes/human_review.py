from langgraph.types import interrupt

from app.workflow.state import WorkflowState


def human_review_node(state: WorkflowState) -> WorkflowState:
    res = interrupt(
        {
            "type": "human_review",
            "run_id": str(state["run_id"]),
            "message": "Human review is required.",
        }
    )

    decision = res.get("decision") if isinstance(res, dict) else res

    return {
        **state,
        "human_decision": decision,
    }
