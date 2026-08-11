from uuid import uuid4

from app.workflow.state import WorkflowState


class TestWorkflowState:

    def test_state_can_hold_workflow_data(self):
        run_id = uuid4()
        document_id = uuid4()

        state: WorkflowState = {
            "run_id": run_id,
            "document_ids": [document_id],
            "documents": [],
            "classification": {},
            "extracted_facts": [],
            "contradictions": [],
            "findings": [],
            "updates": [],
            "error": None,
        }

        assert state["run_id"] == run_id
        assert state["document_ids"] == [document_id]
        assert state["error"] is None