from app.workflow.nodes.reconcile import ReconcileNode


class TestReconcileNode:

    def test_reconcile_does_not_require_human_review_when_all_facts_have_high_confidence(self):
        # Arrange
        node = ReconcileNode()

        state = {
            "extracted_facts": [
                {
                    "field": "party_a",
                    "value": "ABC Ltd",
                    "confidence": 0.95,
                },
                {
                    "field": "party_b",
                    "value": "XYZ Ltd",
                    "confidence": 0.90,
                },
            ],
            "human_review_required": False,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["human_review_required"] is False
        assert result["error"] is None

    def test_reconcile_requires_human_review_when_fact_has_low_confidence(self):
        # Arrange
        node = ReconcileNode()

        state = {
            "extracted_facts": [
                {
                    "field": "party_a",
                    "value": "ABC Ltd",
                    "confidence": 0.95,
                },
                {
                    "field": "party_b",
                    "value": "Unknown",
                    "confidence": 0.60,
                },
            ],
            "human_review_required": False,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["human_review_required"] is True
        assert result["error"] is None

    def test_reconcile_empty_facts_does_not_require_human_review(self):
        # Arrange
        node = ReconcileNode()

        state = {
            "extracted_facts": [],
            "human_review_required": False,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["human_review_required"] is False
        assert result["error"] is None

    def test_reconcile_confidence_boundary_does_not_require_review(self):
        # Arrange
        node = ReconcileNode()

        state = {
            "extracted_facts": [
                {
                    "field": "party_a",
                    "value": "ABC Ltd",
                    "confidence": 0.80,
                }
            ],
            "human_review_required": False,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["human_review_required"] is False

    def test_reconcile_just_below_confidence_boundary_requires_review(self):
        # Arrange
        node = ReconcileNode()

        state = {
            "extracted_facts": [
                {
                    "field": "party_a",
                    "value": "ABC Ltd",
                    "confidence": 0.799,
                }
            ],
            "human_review_required": False,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["human_review_required"] is True

    def test_reconcile_preserves_existing_state(self):
        # Arrange
        node = ReconcileNode()

        state = {
            "run_id": "run-123",
            "classification": {
                "document_type": "contract",
            },
            "extracted_facts": [],
            "human_review_required": False,
            "error": None,
        }

        # Act
        result = node(state)

        # Assert
        assert result["run_id"] == "run-123"
        assert result["classification"]["document_type"] == "contract"