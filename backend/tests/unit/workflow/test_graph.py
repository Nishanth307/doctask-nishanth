from uuid import uuid4

from app.workflow.graph import (
    build_workflow,
    route_after_classify,
    route_after_examine,
    route_after_extract,
    route_after_human_review,
    route_after_reconcile,
    should_retry,
)


class TestWorkflowRouting:

    def test_classify_routes_to_extract_on_success(self):
        state = {
            "run_id": uuid4(),
            "error": None,
            "retry_count": 0,
            "max_retries": 3,
        }

        assert route_after_classify(state) == "extract"

    def test_classify_retries_when_error_exists(self):
        state = {
            "run_id": uuid4(),
            "error": "LLM timeout",
            "retry_count": 1,
            "max_retries": 3,
        }

        assert route_after_classify(state) == "classify"

    def test_classify_fails_after_max_retries(self):
        state = {
            "run_id": uuid4(),
            "error": "LLM timeout",
            "retry_count": 3,
            "max_retries": 3,
        }

        assert route_after_classify(state) == "failed"

    def test_reconcile_routes_to_examine_without_human_review(self):
        state = {
            "run_id": uuid4(),
            "human_review_required": False,
        }

        assert route_after_reconcile(state) == "examine"

    def test_reconcile_routes_to_human_review(self):
        state = {
            "run_id": uuid4(),
            "human_review_required": True,
        }

        assert route_after_reconcile(state) == "human_review"

    def test_human_approval_routes_to_examine(self):
        state = {
            "run_id": uuid4(),
            "human_decision": "approve",
        }

        assert route_after_human_review(state) == "examine"

    def test_human_rejection_routes_to_revise(self):
        state = {
            "run_id": uuid4(),
            "human_decision": "reject",
        }

        assert route_after_human_review(state) == "revise"

    def test_graph_compiles(self):
        workflow = build_workflow()

        assert workflow is not None

    def test_workflow_execution_with_checkpoint(self):
        # Run checkpointer setup to ensure tables exist
        from app.workflow.checkpointer import create_checkpointer
        cp = create_checkpointer()
        cp.setup()

        workflow = build_workflow()
        run_id = uuid4()

        initial_state = {
            "run_id": run_id,
            "document_ids": [uuid4()],
            "documents": [],
            "classification": {},
            "extracted_facts": [],
            "contradictions": [],
            "findings": [],
            "updates": [],
            "error": None,
            "human_review_required": False,
        }

        config = {
            "configurable": {
                "thread_id": str(run_id),
            }
        }

        result = workflow.invoke(
            initial_state,
            config=config,
        )

        assert result["run_id"] == run_id
    
    def test_route_after_reconcile_requires_human_review(self):
        state = {
            "human_review_required": True,
        }

        assert route_after_reconcile(state) == "human_review"


    def test_route_after_reconcile_continues_without_human_review(self):
        state = {
            "human_review_required": False,
        }

        assert route_after_reconcile(state) == "examine"

    def test_should_retry_when_error_and_retries_remaining(self):
        state = {
            "error": "LLM unavailable",
            "retry_count": 1,
            "max_retries": 3,
        }

        assert should_retry(state) is True

    def test_should_not_retry_when_no_error(self):
        state = {
            "error": None,
            "retry_count": 1,
            "max_retries": 3,
        }

        assert should_retry(state) is False

    def test_should_not_retry_after_max_retries(self):
        state = {
            "error": "LLM unavailable",
            "retry_count": 3,
            "max_retries": 3,
        }

        assert should_retry(state) is False

    def test_route_after_extract_on_success(self):
        state = {
            "error": None,
            "retry_count": 0,
            "max_retries": 3,
        }

        assert route_after_extract(state) == "reconcile"

    def test_route_after_extract_retries_on_failure(self):
        state = {
            "error": "LLM unavailable",
            "retry_count": 1,
            "max_retries": 3,
        }

        assert route_after_extract(state) == "extract"

    def test_route_after_extract_fails_after_max_retries(self):
        state = {
            "error": "LLM unavailable",
            "retry_count": 3,
            "max_retries": 3,
        }

        assert route_after_extract(state) == "failed"

    def test_route_after_examine_on_success(self):
        state = {
            "error": None,
            "retry_count": 0,
            "max_retries": 3,
        }

        assert route_after_examine(state) == "update"

    def test_route_after_examine_retries_on_failure(self):
        state = {
            "error": "LLM unavailable",
            "retry_count": 1,
            "max_retries": 3,
        }

        assert route_after_examine(state) == "examine"

    def test_route_after_examine_fails_after_max_retries(self):
        state = {
            "error": "LLM unavailable",
            "retry_count": 3,
            "max_retries": 3,
        }

        assert route_after_examine(state) == "failed"