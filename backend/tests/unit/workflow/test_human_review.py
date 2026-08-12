from uuid import uuid4

import pytest
from langgraph.types import Command

from app.workflow.graph import build_workflow


class TestHumanReview:

    def test_workflow_interrupts_for_human_review(self):
        # Arrange
        workflow = build_workflow()

        run_id = uuid4()

        state = {
            "run_id": run_id,
            "document_ids": [],
            "documents": [],
            "classification": {},
            "extracted_facts": [],
            "contradictions": [],
            "findings": [],
            "updates": [],
            "human_review_required": True,
            "human_decision": None,
            "retry_count": 0,
            "max_retries": 3,
            "error": None,
        }

        config = {
            "configurable": {
                "thread_id": str(run_id),
            }
        }

        # Act
        result = workflow.invoke(state, config)

        # Assert
        assert "__interrupt__" in result

        interrupt = result["__interrupt__"][0]

        assert interrupt.value["type"] == "human_review"
        assert interrupt.value["run_id"] == str(run_id)

    def test_workflow_resumes_after_human_approval(self):
        # Arrange
        workflow = build_workflow()

        run_id = uuid4()

        state = {
            "run_id": run_id,
            "document_ids": [],
            "documents": [],
            "classification": {},
            "extracted_facts": [],
            "contradictions": [],
            "findings": [],
            "updates": [],
            "human_review_required": True,
            "human_decision": None,
            "retry_count": 0,
            "max_retries": 3,
            "error": None,
        }

        config = {
            "configurable": {
                "thread_id": str(run_id),
            }
        }

        # First execution → interrupt
        interrupted = workflow.invoke(state, config)

        assert "__interrupt__" in interrupted

        # Act → resume
        result = workflow.invoke(
            Command(resume="approve"),
            config,
        )

        # Assert
        assert result["human_decision"] == "approve"

    def test_workflow_resumes_after_human_rejection(self):
        # Arrange
        workflow = build_workflow()

        run_id = uuid4()

        state = {
            "run_id": run_id,
            "document_ids": [],
            "documents": [],
            "classification": {},
            "extracted_facts": [],
            "contradictions": [],
            "findings": [],
            "updates": [],
            "human_review_required": True,
            "human_decision": None,
            "retry_count": 0,
            "max_retries": 3,
            "error": None,
        }

        config = {
            "configurable": {
                "thread_id": str(run_id),
            }
        }

        workflow.invoke(state, config)

        # Act
        result = workflow.invoke(
            Command(resume="reject"),
            config,
        )

        # Assert
        assert result["human_decision"] == "reject"