from langgraph.types import interrupt

from app.workflow.state import WorkflowState


def human_review_node(state: WorkflowState) -> WorkflowState:
    decision = interrupt(
        {
            "type": "human_review",
            "run_id": str(state["run_id"]),
            "message": "Human review is required.",
        }
    )

    return {
        **state,
        "human_decision": decision,
    }
