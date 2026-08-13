from typing import Any
from uuid import uuid4

from langgraph.types import Command

from app.workflow.graph import build_workflow


class WorkflowService:
    def __init__(self, graph=None) -> None:
        self.graph = graph or build_workflow()

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

        return {
            "thread_id": thread_id,
            "state": result,
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

        return {
            "thread_id": thread_id,
            "state": result,
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