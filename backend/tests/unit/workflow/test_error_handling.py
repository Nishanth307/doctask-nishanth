"""Comprehensive unit tests for universal LangGraph error handling and visibility.

Verifies:
- Error classification across all categories (LLM, TIMEOUT, RATE_LIMIT, PERMANENT, TRANSIENT, etc.)
- Secret redaction (Gemini, OpenAI, Bearer tokens, connection strings)
- Universal node wrapper error capture and attempt tracking
- Execution history accumulation
- Checkpointing and diagnostic preservation
- Node-specific retry rewinding to predecessor without re-running earlier completed nodes
- Permanent errors bypassing auto-retry
"""
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END

from app.core.errors import (
    ErrorCategory,
    classify_error,
    sanitize_error_message,
)
from app.workflow.graph import (
    UPSTREAM_NODE_MAP,
    _make_emitting_wrapper,
    should_retry,
)
from app.workflow.service import WorkflowService


# =========================================================================
# 1. Error Classification & Secret Redaction Tests
# =========================================================================

class TestErrorClassification:

    def test_classify_rate_limit(self):
        cat, retryable, msg = classify_error("Resource has been exhausted (e.g. check quota) 429")
        assert cat == ErrorCategory.RATE_LIMIT
        assert retryable is True

    def test_classify_timeout(self):
        cat, retryable, msg = classify_error("Request timed out after 30000ms: deadline exceeded")
        assert cat == ErrorCategory.TIMEOUT
        assert retryable is True

    def test_classify_database_error(self):
        cat, retryable, msg = classify_error("OperationalError: connection to server was lost psycopg2")
        assert cat == ErrorCategory.DATABASE
        assert retryable is True

    def test_classify_permanent_auth_error(self):
        cat, retryable, msg = classify_error("Invalid API key provided: authentication failed 401 Unauthorized")
        assert cat in (ErrorCategory.CONFIGURATION, ErrorCategory.PERMANENT)
        assert retryable is False

    def test_classify_validation_error(self):
        cat, retryable, msg = classify_error("ValidationError: document payload missing required schema fields")
        assert cat == ErrorCategory.VALIDATION
        assert retryable is False

    def test_classify_llm_model_error(self):
        cat, retryable, msg = classify_error("Gemini API generation stopped: SAFETY block triggered")
        assert cat == ErrorCategory.LLM

    def test_classify_storage_error(self):
        cat, retryable, msg = classify_error("FileNotFoundError: bucket or object not found in GCS storage")
        assert cat == ErrorCategory.STORAGE

    def test_classify_unknown(self):
        cat, retryable, msg = classify_error("Some obscure internal exception")
        assert cat == ErrorCategory.UNKNOWN
        assert retryable is True


class TestSecretSanitization:

    def test_redacts_gemini_api_keys(self):
        raw = "Error communicating with AIzaSyAbC1234567890defGHIJklMNopQRstUVw: quota limit"
        sanitized = sanitize_error_message(raw)
        assert "AIzaSy" not in sanitized
        assert "[REDACTED_API_KEY]" in sanitized

    def test_redacts_openai_api_keys(self):
        raw = "Failed call with key sk-1234567890abcdef1234567890abcdef12"
        sanitized = sanitize_error_message(raw)
        assert "sk-1234" not in sanitized
        assert "[REDACTED_API_KEY]" in sanitized

    def test_redacts_bearer_tokens(self):
        raw = "Auth header Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 expired"
        sanitized = sanitize_error_message(raw)
        assert "eyJhb" not in sanitized
        assert "Bearer [REDACTED_TOKEN]" in sanitized

    def test_redacts_database_passwords(self):
        raw = "connection failed to postgres://user:SuperSecretPassword123@db.host.com:5432/doctask"
        sanitized = sanitize_error_message(raw)
        assert "SuperSecretPassword123" not in sanitized
        assert "postgres://user:[REDACTED_PASSWORD]@" in sanitized


# =========================================================================
# 2. Universal Node Wrapper Tests
# =========================================================================

class TestNodeWrapper:

    def test_successful_node_records_completion(self):
        def my_node(state):
            return {"data": "hello"}

        wrapped = _make_emitting_wrapper("test_node", my_node)
        state = {"run_id": None, "node_attempts": {}, "execution_history": []}

        output = wrapped(state)
        assert output["data"] == "hello"
        assert output["current_node"] == "test_node"
        assert output["node_attempts"]["test_node"] == 1
        assert len(output["execution_history"]) == 1
        record = output["execution_history"][0]
        assert record["node_name"] == "test_node"
        assert record["status"] == "completed"
        assert output["error"] is None

    def test_failing_node_captures_error_and_does_not_raise(self):
        def failing_node(state):
            raise TimeoutError("Deadline exceeded after 5000ms")

        wrapped = _make_emitting_wrapper("failing_node", failing_node)
        state = {"run_id": None, "node_attempts": {}, "execution_history": []}

        output = wrapped(state)
        assert output["status"] == "failed"
        assert output["current_node"] == "failing_node"
        assert output["node_attempts"]["failing_node"] == 1
        assert len(output["execution_history"]) == 1

        record = output["execution_history"][0]
        assert record["status"] == "failed"
        assert record["error_type"] == ErrorCategory.TIMEOUT.value
        assert record["retryable"] is True

        last_error = output["last_error"]
        assert last_error is not None
        assert last_error["node_name"] == "failing_node"
        assert last_error["error_type"] == ErrorCategory.TIMEOUT.value
        assert "Deadline exceeded" in last_error["error_message"]

    def test_permanent_error_marks_not_retryable(self):
        def unauthorized_node(state):
            raise PermissionError("401 Unauthorized: Invalid API key")

        wrapped = _make_emitting_wrapper("auth_node", unauthorized_node)
        state = {"run_id": None, "node_attempts": {}, "execution_history": []}

        output = wrapped(state)
        assert output["status"] == "failed"
        assert output["last_error"]["retryable"] is False
        assert should_retry(output) is False

    def test_attempt_counter_increments_per_node(self):
        call_count = 0

        def flaky_node(state):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Transient glitch")
            return {"data": "fixed"}

        wrapped = _make_emitting_wrapper("flaky_node", flaky_node)
        state = {"run_id": None, "node_attempts": {}, "execution_history": []}

        # First attempt
        state1 = wrapped(state)
        assert state1["node_attempts"]["flaky_node"] == 1
        assert state1["status"] == "failed"

        # Second attempt
        state2 = wrapped(state1)
        assert state2["node_attempts"]["flaky_node"] == 2
        assert state2["data"] == "fixed"
        assert state2["error"] is None
        assert len(state2["execution_history"]) == 2


# =========================================================================
# 3. Node-Specific Retry & Checkpoint Rewind Tests
# =========================================================================

class TestNodeSpecificRetry:

    def test_retry_node_does_not_re_execute_prior_nodes(self):
        """Verify that retrying node 2 invokes ONLY node 2 and beyond,

        leaving node 1 untouched with its checkpoint preserved.
        """
        node1_executions = 0
        node2_executions = 0
        should_node2_fail = True

        def step1(state):
            nonlocal node1_executions
            node1_executions += 1
            return {"step1_data": "done"}

        def step2(state):
            nonlocal node2_executions
            node2_executions += 1
            if should_node2_fail:
                raise RuntimeError("LLM rate limit reached")
            return {"step2_data": "done"}

        from typing import TypedDict

        class RetryTestState(TypedDict, total=False):
            run_id: str | None
            step1_data: str
            step2_data: str
            error: str | None
            status: str
            last_error: dict | None
            node_attempts: dict
            execution_history: list
            current_node: str

        builder = StateGraph(RetryTestState)
        builder.add_node("classify", _make_emitting_wrapper("classify", step1))
        builder.add_node("extract", _make_emitting_wrapper("extract", step2))
        builder.add_edge(START, "classify")
        builder.add_conditional_edges("classify", lambda s: "extract" if not s.get("error") else "failed")
        builder.add_conditional_edges("extract", lambda s: END if not s.get("error") else END)

        checkpointer = MemorySaver()
        graph = builder.compile(checkpointer=checkpointer)
        service = WorkflowService(graph=graph)

        thread_id = str(uuid4())

        # 1. Initial run: step 1 succeeds, step 2 fails
        result1 = service.start(state={"run_id": None}, thread_id=thread_id)
        assert node1_executions == 1
        assert node2_executions == 1
        assert result1["state"]["status"] == "failed"
        assert result1["state"]["last_error"]["node_name"] == "extract"

        # 2. Resolve error condition
        should_node2_fail = False

        # 3. Retry node 2 specifically
        result2 = service.retry_node(thread_id=thread_id, node_name="extract")

        # Step 1 MUST NOT have been re-executed!
        assert node1_executions == 1, "Prior completed node was re-executed during node retry!"
        # Step 2 was re-executed and succeeded
        assert node2_executions == 2
        assert result2["state"]["step1_data"] == "done"
        assert result2["state"]["step2_data"] == "done"
        assert result2["state"]["error"] is None

    def test_upstream_node_map_covers_all_nodes(self):
        """Ensure all workflow nodes have an upstream predecessor defined for checkpoint rewind."""
        expected_nodes = [
            "classify",
            "extract",
            "reconcile",
            "human_review",
            "revise",
            "examine",
            "generate_suggested_changes",
            "findings_review",
            "apply_edits",
            "validate_edits",
            "commit",
            "update",
        ]
        for node in expected_nodes:
            assert node in UPSTREAM_NODE_MAP, f"Missing upstream mapping for {node}"
