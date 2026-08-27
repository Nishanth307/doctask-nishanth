from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from langgraph.types import Command

if TYPE_CHECKING:
    from app.services.workflow_result_service import WorkflowResultService

from app.workflow.graph import build_workflow

_cached_workflow = None


def get_workflow_graph():
    global _cached_workflow
    if _cached_workflow is None:
        _cached_workflow = build_workflow()
    return _cached_workflow


class WorkflowService:
    def __init__(
        self,
        graph=None,
        result_service: "WorkflowResultService" | None = None,
    ) -> None:
        self.graph = graph or get_workflow_graph()
        self.result_service = result_service

    def start(
        self,
        state: dict[str, Any],
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        thread_id = thread_id or str(uuid4())

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        result = self.graph.invoke(
            state,
            config=config,
        )

        state_values = dict(result) if isinstance(result, dict) else {}
        try:
            snapshot = self.graph.get_state(config)
            if hasattr(snapshot, "values") and isinstance(snapshot.values, dict) and snapshot.values:
                state_values = {**state_values, **snapshot.values}
        except Exception:
            pass

        return {
            "thread_id": thread_id,
            "state": state_values,
        }

    def resume(
        self,
        thread_id: str,
        decision: str,
    ) -> dict[str, Any]:
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        result = self.graph.invoke(
            Command(
                resume={
                    "decision": decision,
                }
            ),
            config=config,
        )

        state_values = dict(result) if isinstance(result, dict) else {}
        try:
            snapshot = self.graph.get_state(config)
            if hasattr(snapshot, "values") and isinstance(snapshot.values, dict) and snapshot.values:
                state_values = {**state_values, **snapshot.values}
        except Exception:
            pass

        return {
            "thread_id": thread_id,
            "state": state_values,
        }

    def get_state(
        self,
        thread_id: str,
    ) -> Any:
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        return self.graph.get_state(config)

    def persist_result(
        self,
        run_id: UUID,
        state: dict[str, Any],
    ):
        if self.result_service is None:
            raise RuntimeError(
                "WorkflowResultService is not configured"
            )

        return self.result_service.create_result(
            run_id=run_id,
            state=state,
        )