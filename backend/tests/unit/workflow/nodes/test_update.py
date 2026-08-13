from app.llm.schemas import ExaminationResult
from app.workflow.nodes.update import UpdateNode


class TestUpdateNode:

    def test_update_success(self):
        # Arrange
        node = UpdateNode()

        examination = ExaminationResult(
            is_valid=True,
            confidence=0.95,
            issues=[],
            summary="The document is valid.",
        )

        state = {
            "run_id": "run-123",
            "examination": examination,
            "status": None,
            "updates": [],
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["status"] == "completed"
        assert result["error"] is None

        assert result["updates"]["status"] == "completed"
        assert result["updates"]["examination_valid"] is True
        assert result["updates"]["examination_confidence"] == 0.95
        assert result["updates"]["issues"] == []
        assert result["updates"]["summary"] == (
            "The document is valid."
        )

    def test_update_with_examination_issues(self):
        # Arrange
        node = UpdateNode()

        examination = ExaminationResult(
            is_valid=False,
            confidence=0.72,
            issues=[
                "Party name does not match.",
                "Contract date is missing.",
            ],
            summary="The document contains issues.",
        )

        state = {
            "examination": examination,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["status"] == "completed"
        assert result["updates"]["examination_valid"] is False
        assert result["updates"]["examination_confidence"] == 0.72

        assert result["updates"]["issues"] == [
            "Party name does not match.",
            "Contract date is missing.",
        ]

        assert result["updates"]["summary"] == (
            "The document contains issues."
        )

    def test_update_fails_when_examination_is_missing(self):
        # Arrange
        node = UpdateNode()

        state = {
            "run_id": "run-123",
            "examination": None,
            "status": None,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["status"] == "failed"
        assert result["error"] == (
            "Examination result is missing"
        )

    def test_update_preserves_existing_state(self):
        # Arrange
        node = UpdateNode()

        examination = ExaminationResult(
            is_valid=True,
            confidence=0.90,
            issues=[],
            summary="Valid document.",
        )

        state = {
            "run_id": "run-123",
            "human_decision": "approve",
            "classification": {
                "document_type": "contract",
            },
            "extracted_facts": [
                {
                    "field": "party_a",
                    "value": "ABC Ltd",
                    "confidence": 0.95,
                }
            ],
            "examination": examination,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["run_id"] == "run-123"
        assert result["human_decision"] == "approve"
        assert result["classification"]["document_type"] == "contract"
        assert len(result["extracted_facts"]) == 1