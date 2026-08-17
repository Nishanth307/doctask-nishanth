from uuid import uuid4
from unittest.mock import MagicMock
import pytest

from app.core.constants import FindingSeverity, ReviewDecision
from app.persistence.models.finding import Finding
from app.persistence.repositories.finding import FindingRepository
from app.services.finding_service import FindingService


class TestFindingService:

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock(spec=FindingRepository)
        repo.db = MagicMock()
        return repo

    @pytest.fixture
    def service(self, mock_repo):
        return FindingService(mock_repo)

    def test_sync_contradiction_creates_new(self, service, mock_repo):
        run_id = uuid4()
        mock_repo.get_by_run_id.return_value = []

        contradictions = [
            {
                "field": "contract term",
                "semantic_key": "agreement.duration",
                "values": [
                    {"source_document": "v1.pdf", "value": "12 months"},
                    {"source_document": "v2.pdf", "value": "36 months"},
                ]
            }
        ]

        service.sync_contradiction_findings(run_id, contradictions)

        # Should invoke create on repo
        mock_repo.create.assert_called_once()
        created_finding = mock_repo.create.call_args[0][0]
        assert created_finding.run_id == run_id
        assert created_finding.title == "Conflicting contract term"
        assert created_finding.severity == FindingSeverity.ERROR
        assert created_finding.review_decision == ReviewDecision.PENDING
        assert created_finding.finding_metadata["semantic_key"] == "agreement.duration"

    def test_sync_contradiction_updates_existing_pending(self, service, mock_repo):
        run_id = uuid4()
        existing = Finding(
            run_id=run_id,
            title="Old title",
            description="Old desc",
            severity=FindingSeverity.ERROR,
            review_decision=ReviewDecision.PENDING,
            finding_metadata={"type": "contradiction", "semantic_key": "agreement.duration"}
        )
        mock_repo.get_by_run_id.return_value = [existing]

        contradictions = [
            {
                "field": "contract term",
                "semantic_key": "agreement.duration",
                "values": [
                    {"source_document": "v1.pdf", "value": "12 months"},
                    {"source_document": "v2.pdf", "value": "36 months"},
                ]
            }
        ]

        service.sync_contradiction_findings(run_id, contradictions)

        mock_repo.create.assert_not_called()
        # Verify existing was modified in-place
        assert existing.title == "Conflicting contract term"
        assert "Conflicting values were found" in existing.description


    def test_sync_contradiction_preserves_human_decision(self, service, mock_repo):
        run_id = uuid4()
        existing = Finding(
            run_id=run_id,
            title="Conflicting contract term",
            description="12 months vs 36 months",
            severity=FindingSeverity.ERROR,
            review_decision=ReviewDecision.APPROVED,
            finding_metadata={"type": "contradiction", "semantic_key": "agreement.duration"}
        )
        mock_repo.get_by_run_id.return_value = [existing]

        contradictions = [
            {
                "field": "contract term",
                "semantic_key": "agreement.duration",
                "values": [
                    {"source_document": "v1.pdf", "value": "12 months"},
                    {"source_document": "v2.pdf", "value": "36 months"},
                ]
            }
        ]

        service.sync_contradiction_findings(run_id, contradictions)

        # Existing should remain approved, title and desc should NOT be rewritten (no updates)
        assert existing.review_decision == ReviewDecision.APPROVED
        assert existing.title == "Conflicting contract term"
        mock_repo.create.assert_not_called()

    def test_sync_contradiction_deletes_stale_pending(self, service, mock_repo):
        run_id = uuid4()
        stale_pending = Finding(
            run_id=run_id,
            title="Conflicting contract term",
            description="12 months vs 36 months",
            severity=FindingSeverity.ERROR,
            review_decision=ReviewDecision.PENDING,
            finding_metadata={"type": "contradiction", "semantic_key": "agreement.duration"}
        )
        mock_repo.get_by_run_id.return_value = [stale_pending]

        # No contradictions in state now
        service.sync_contradiction_findings(run_id, [])

        mock_repo.delete.assert_called_once_with(stale_pending)

    def test_sync_checklist_creates_new(self, service, mock_repo):
        run_id = uuid4()
        mock_repo.get_by_run_id.return_value = []

        issues = ["Contract term must not exceed 24 months."]

        service.sync_checklist_findings(run_id, issues)

        mock_repo.create.assert_called_once()
        created = mock_repo.create.call_args[0][0]
        assert created.run_id == run_id
        assert created.title == "Policy Violation"
        assert created.description == "Contract term must not exceed 24 months."
        assert created.review_decision == ReviewDecision.PENDING

    def test_sync_checklist_deletes_stale_pending(self, service, mock_repo):
        run_id = uuid4()
        stale_pending = Finding(
            run_id=run_id,
            title="Policy Violation",
            description="Contract term must not exceed 24 months.",
            severity=FindingSeverity.ERROR,
            review_decision=ReviewDecision.PENDING,
            finding_metadata={"type": "violation"}
        )
        mock_repo.get_by_run_id.return_value = [stale_pending]

        # Issue resolved, no issues in state now
        service.sync_checklist_findings(run_id, [])

        mock_repo.delete.assert_called_once_with(stale_pending)
