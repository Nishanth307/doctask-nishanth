from collections.abc import Callable

from app.workflow.state import WorkflowState


def execute_with_retry(
    node: Callable[[WorkflowState], WorkflowState],
    state: WorkflowState,
) -> WorkflowState:
    retry_count = state.get("retry_count", 0)

    try:
        return node(state)

    except Exception as exc:  # noqa: BLE001
        return {
            **state,
            "retry_count": retry_count + 1,
            "error": str(exc),
        }
