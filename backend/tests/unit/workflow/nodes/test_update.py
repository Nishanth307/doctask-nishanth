from unittest.mock import MagicMock
from uuid import uuid4

from app.workflow.nodes.update import UpdateNode


class TestUpdateNode:

    def test_update_persists_workflow_result(self):
        # Arrange
        repository = MagicMock()

        result_id = uuid4()

        persisted_result = MagicMock()
        persisted_result.id = result_id

        repository.create.return_value = persisted_result

        node = UpdateNode(repository)

        run_id = uuid4()

        state = {
            "run_id": run_id,
            "classification": {
                "document_type": "contract",
                "confidence": 0.95,
            },
            "extracted_facts": [
                {
                    "field": "party_a",
                    "value": "ABC Ltd",
                    "confidence": 0.95,
                }
            ],
            "human_review_required": False,
            "examination": {
                "is_valid": True,
                "confidence": 0.95,
                "issues": [],
                "summary": "Valid.",
            },
            "human_decision": None,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        repository.create.assert_called_once()

        persisted = repository.create.call_args.args[0]

        assert persisted.run_id == run_id
        assert persisted.status == "completed"
        assert persisted.classification == state["classification"]
        assert persisted.extracted_facts == state["extracted_facts"]
        assert persisted.examination == state["examination"]

        assert result["status"] == "completed"
        assert result["result_id"] == result_id
        assert result["error"] is None

    def test_update_persists_human_decision(self):
        # Arrange
        repository = MagicMock()

        persisted_result = MagicMock()
        persisted_result.id = uuid4()

        repository.create.return_value = persisted_result

        node = UpdateNode(repository)

        state = {
            "run_id": uuid4(),
            "classification": {},
            "extracted_facts": [],
            "human_review_required": True,
            "human_decision": "approve",
            "examination": {
                "is_valid": True,
                "confidence": 0.90,
                "issues": [],
                "summary": "Approved after review.",
            },
            "error": None,
        }

        # Act
        node(state)

        # Assert
        persisted = repository.create.call_args.args[0]

        assert persisted.human_decision == "approve"

    def test_update_sets_completed_status(self):
        # Arrange
        repository = MagicMock()

        persisted_result = MagicMock()
        persisted_result.id = uuid4()

        repository.create.return_value = persisted_result

        node = UpdateNode(repository)

        state = {
            "run_id": uuid4(),
            "classification": {},
            "extracted_facts": [],
            "human_review_required": False,
            "examination": {},
            "human_decision": None,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["status"] == "completed"

    def test_update_propagates_repository_exception(self):
        # Arrange
        repository = MagicMock()
        repository.create.side_effect = RuntimeError(
            "Database unavailable"
        )

        node = UpdateNode(repository)

        state = {
            "run_id": uuid4(),
            "classification": {},
            "extracted_facts": [],
            "human_review_required": False,
            "examination": {},
            "human_decision": None,
            "error": None,
        }

        # Act & Assert
        try:
            node(state)
        except RuntimeError as exc:
            assert str(exc) == "Database unavailable"
        else:
            raise AssertionError(
                "Expected RuntimeError"
            )