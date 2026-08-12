from uuid import uuid4 

from app.workflow.graph import (
    build_workflow,
    route_after_classify,
    classify_node
)

class TestClassifyRetry:

    def test_classify_success_clears_error(self):
        # Arrange
        state = {
            "run_id": uuid4(),
            "error": None,
            "retry_count": 0,
            "max_retries": 3,
            "simulate_failure": False,
        }

        # Act
        result = classify_node(state)

        # Assert
        assert result["error"] is None
        assert result["retry_count"] == 0

    def test_classify_failure_increments_retry_count(self):
        # Arrange
        state = {
            "run_id": uuid4(),
            "error": None,
            "retry_count": 0,
            "max_retries": 3,
            "simulate_failure": True,
        }

        # Act
        result = classify_node(state)

        # Assert
        assert result["error"] == "Classification failed"
        assert result["retry_count"] == 1

    def test_classify_retries_when_retry_limit_not_reached(self):
        # Arrange
        state = {
            "run_id": uuid4(),
            "error": "Classification failed",
            "retry_count": 1,
            "max_retries": 3,
        }

        # Act
        result = route_after_classify(state)

        # Assert
        assert result == "classify"

    def test_classify_retries_on_second_attempt(self):
        # Arrange
        state = {
            "run_id": uuid4(),
            "error": "Classification failed",
            "retry_count": 2,
            "max_retries": 3,
        }

        # Act
        result = route_after_classify(state)

        # Assert
        assert result == "classify"

    def test_classify_fails_when_max_retries_reached(self):
        # Arrange
        state = {
            "run_id": uuid4(),
            "error": "Classification failed",
            "retry_count": 3,
            "max_retries": 3,
        }

        # Act
        result = route_after_classify(state)

        # Assert
        assert result == "failed"

    def test_classify_failure_with_zero_max_retries_goes_to_failed(self):
        # Arrange
        state = {
            "run_id": uuid4(),
            "error": "Classification failed",
            "retry_count": 0,
            "max_retries": 0,
        }

        # Act
        result = route_after_classify(state)

        # Assert
        assert result == "failed"

class TestRetryWorkflow:

    def test_successful_classification_continues_to_extract(self):
        # Arrange
        workflow = build_workflow()

        state = {
            "run_id": uuid4(),
            "document_ids": [],
            "documents": [],
            "classification": {},
            "extracted_facts": [],
            "contradictions": [],
            "findings": [],
            "updates": [],
            "human_review_required": False,
            "human_decision": None,
            "retry_count": 0,
            "max_retries": 3,
            "error": None,
            "simulate_failure": False,
        }

        config = {
            "configurable": {
                "thread_id": str(state["run_id"]),
            }
        }

        # Act
        result = workflow.invoke(state, config)

        # Assert
        assert result["error"] is None