from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langgraph.types import Command

from app.workflow.service import WorkflowService


class TestWorkflowService:

    def test_start_creates_thread_id_when_not_provided(self):
        graph = MagicMock()

        graph.invoke.return_value = {
            "status": "completed",
        }

        service = WorkflowService(graph=graph)

        state = {
            "run_id": uuid4(),
        }

        result = service.start(state)

        assert result["thread_id"]
        assert result["state"]["status"] == "completed"

        graph.invoke.assert_called_once()

        _, kwargs = graph.invoke.call_args

        assert kwargs["config"]["configurable"]["thread_id"] == (
            result["thread_id"]
        )

    def test_start_uses_existing_thread_id(self):
        graph = MagicMock()

        graph.invoke.return_value = {
            "status": "completed",
        }

        service = WorkflowService(graph=graph)

        thread_id = str(uuid4())

        result = service.start(
            state={"run_id": uuid4()},
            thread_id=thread_id,
        )

        assert result["thread_id"] == thread_id

        _, kwargs = graph.invoke.call_args

        assert (
            kwargs["config"]["configurable"]["thread_id"]
            == thread_id
        )

    def test_resume_sends_human_decision(self):
        graph = MagicMock()

        graph.invoke.return_value = {
            "status": "completed",
            "human_decision": "approve",
        }

        service = WorkflowService(graph=graph)

        thread_id = str(uuid4())

        result = service.resume(
            thread_id=thread_id,
            decision="approve",
        )

        assert result["thread_id"] == thread_id
        assert result["state"]["human_decision"] == "approve"

        graph.invoke.assert_called_once()

        args, kwargs = graph.invoke.call_args

        command = args[0]

        assert isinstance(command, Command)
        assert command.resume == {
            "decision": "approve",
        }

        assert (
            kwargs["config"]["configurable"]["thread_id"]
            == thread_id
        )

    def test_resume_rejects_decision(self):
        graph = MagicMock()

        graph.invoke.return_value = {
            "status": "completed",
            "human_decision": "reject",
        }

        service = WorkflowService(graph=graph)

        thread_id = str(uuid4())

        result = service.resume(
            thread_id=thread_id,
            decision="reject",
        )

        assert result["state"]["human_decision"] == "reject"

    def test_get_state_uses_thread_id(self):
        graph = MagicMock()

        expected_state = MagicMock()
        graph.get_state.return_value = expected_state

        service = WorkflowService(graph=graph)

        thread_id = str(uuid4())

        result = service.get_state(thread_id)

        assert result is expected_state

        graph.get_state.assert_called_once()

        args = graph.get_state.call_args.args

        config = args[0]

        assert (
            config["configurable"]["thread_id"]
            == thread_id
        )

    def test_start_propagates_graph_exception(self):
        graph = MagicMock()
        graph.invoke.side_effect = RuntimeError("Workflow failed")

        service = WorkflowService(graph=graph)

        with pytest.raises(
            RuntimeError,
            match="Workflow failed",
        ):
            service.start(
                state={"run_id": uuid4()},
                thread_id="thread-123",
            )

    def test_resume_propagates_graph_exception(self):
        graph = MagicMock()
        graph.invoke.side_effect = RuntimeError("Resume failed")

        service = WorkflowService(graph=graph)

        with pytest.raises(
            RuntimeError,
            match="Resume failed",
        ):
            service.resume(
                thread_id="thread-123",
                decision="approve",
            )