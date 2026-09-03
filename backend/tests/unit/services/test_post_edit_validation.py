"""Tests for PostEditValidationEngine.

Covers:
- Approved + applied: proposed_value present in final doc → PASSED
- Rejected: original_value still present → PASSED  
- Rejected: original_value missing (unexpected mutation) → FAILED
- Approved + failed application: finding marked FAILED
- Pending findings: SKIPPED
- Unexpected section change detection
- Overall passed/failed aggregate
"""
import pytest
from uuid import uuid4
from types import SimpleNamespace

from app.services.mutation_service import (
    ChangeRecord,
    DocumentMutationEngine,
    MutationResult,
    compute_section_hashes,
)
from app.services.validation_service import PostEditValidationEngine
from app.core.constants import ReviewDecision, ValidationStatus


def _make_finding(
    *,
    fid=None,
    review_decision=ReviewDecision.APPROVED,
    original_value=None,
    proposed_value=None,
    proposed_edit=None,
    source_location=None,
):
    return SimpleNamespace(
        id=fid or uuid4(),
        review_decision=review_decision,
        original_value=original_value,
        proposed_value=proposed_value,
        proposed_edit=proposed_edit,
        source_location=source_location,
    )


def _make_change_record(
    finding_id: str,
    application_status: str,
    original_value: str = "",
    new_value: str = "",
    run_id: str = "",
) -> ChangeRecord:
    return ChangeRecord(
        change_id=str(uuid4()),
        finding_id=finding_id,
        run_id=run_id or str(uuid4()),
        document_id=None,
        source_location=None,
        original_value=original_value,
        new_value=new_value,
        proposed_edit=None,
        reviewer_decision="approved",
        application_status=application_status,
        reason="test",
        applied_at="2026-01-01T00:00:00Z",
    )


class TestPostEditValidationEngine:
    def setup_method(self):
        self.engine = PostEditValidationEngine()

    def _make_mutation_result(
        self,
        original_text: str,
        mutated_text: str,
        applied_changes=None,
        rejected_changes=None,
        failed_changes=None,
    ) -> MutationResult:
        result = MutationResult(
            original_text=original_text,
            mutated_text=mutated_text,
            applied_changes=applied_changes or [],
            rejected_changes=rejected_changes or [],
            failed_changes=failed_changes or [],
            section_hashes_before=compute_section_hashes(original_text),
            section_hashes_after=compute_section_hashes(mutated_text),
        )
        return result

    def test_approved_and_applied_proposed_value_present_passes(self):
        """Approved finding: proposed_value present, original absent → PASSED."""
        finding_id = uuid4()
        finding = _make_finding(
            fid=finding_id,
            original_value="45 days",
            proposed_value="30 days",
        )
        original_text = "Payment due within 45 days."
        mutated_text = "Payment due within 30 days."

        cr = _make_change_record(str(finding_id), "applied", "45 days", "30 days")
        cr.source_location = "document"  # match the section hash key
        mutation_result = self._make_mutation_result(original_text, mutated_text, applied_changes=[cr])

        result = self.engine.validate([finding], mutation_result)

        assert result.passed is True
        assert len(result.finding_results) == 1
        fr = result.finding_results[0]
        assert fr.validation_status == "passed"

    def test_rejected_original_preserved_passes(self):
        """Rejected finding: original_value still in document → PASSED."""
        finding_id = uuid4()
        finding = _make_finding(
            fid=finding_id,
            review_decision=ReviewDecision.REJECTED,
            original_value="36 months",
            proposed_value="24 months",
        )
        text = "The contract term is 36 months."
        cr = _make_change_record(str(finding_id), "rejected", "36 months", "24 months")
        mutation_result = self._make_mutation_result(text, text, rejected_changes=[cr])

        result = self.engine.validate([finding], mutation_result)

        assert result.passed is True
        fr = result.finding_results[0]
        assert fr.validation_status == "passed"
        assert "preserved" in fr.reason.lower()

    def test_rejected_original_missing_fails(self):
        """If reviewer rejected but original_value is gone, that's a validation failure."""
        finding_id = uuid4()
        finding = _make_finding(
            fid=finding_id,
            review_decision=ReviewDecision.REJECTED,
            original_value="36 months",
            proposed_value="24 months",
        )
        original_text = "The contract term is 36 months."
        # Simulate unexpected mutation: 36 months is gone
        mutated_text = "The contract term is 24 months."

        cr = _make_change_record(str(finding_id), "rejected", "36 months", "24 months")
        mutation_result = self._make_mutation_result(original_text, mutated_text, rejected_changes=[cr])

        result = self.engine.validate([finding], mutation_result)

        assert result.passed is False
        fr = result.finding_results[0]
        assert fr.validation_status == "failed"
        assert "unexpected" in fr.reason.lower()

    def test_approved_application_failed_overall_fails(self):
        """Approved finding whose application failed → overall validation fails."""
        finding_id = uuid4()
        finding = _make_finding(
            fid=finding_id,
            original_value="45 days",
            proposed_value="30 days",
        )
        text = "No payment terms in this document."
        cr = _make_change_record(str(finding_id), "failed", "45 days", "30 days")
        mutation_result = self._make_mutation_result(text, text, failed_changes=[cr])

        result = self.engine.validate([finding], mutation_result)

        assert result.passed is False
        fr = result.finding_results[0]
        assert fr.validation_status == "failed"

    def test_pending_finding_is_skipped(self):
        """Pending findings are skipped (not yet decided)."""
        finding_id = uuid4()
        finding = _make_finding(
            fid=finding_id,
            review_decision=ReviewDecision.PENDING,
            original_value="45 days",
            proposed_value="30 days",
        )
        text = "Payment due within 45 days."
        mutation_result = self._make_mutation_result(text, text)

        result = self.engine.validate([finding], mutation_result)

        assert result.passed is True  # No failure from pending
        fr = result.finding_results[0]
        assert fr.validation_status == "skipped"

    def test_approved_no_values_passes(self):
        """Approved finding without original/proposed values → PASSED (no text verification needed)."""
        finding_id = uuid4()
        finding = _make_finding(
            fid=finding_id,
            original_value=None,
            proposed_value=None,
        )
        text = "Some document text."
        cr = _make_change_record(str(finding_id), "applied")
        mutation_result = self._make_mutation_result(text, text, applied_changes=[cr])

        result = self.engine.validate([finding], mutation_result)

        assert result.passed is True
        fr = result.finding_results[0]
        assert fr.validation_status == "passed"

    def test_summary_contains_counts(self):
        """Summary string includes applied/rejected/failed counts."""
        finding_id = uuid4()
        finding = _make_finding(
            fid=finding_id,
            original_value="45 days",
            proposed_value="30 days",
        )
        original = "Pay within 45 days."
        mutated = "Pay within 30 days."
        cr = _make_change_record(str(finding_id), "applied", "45 days", "30 days")
        mutation_result = self._make_mutation_result(original, mutated, applied_changes=[cr])

        result = self.engine.validate([finding], mutation_result)

        assert "1 change(s) applied" in result.summary

    def test_multiple_findings_mixed(self):
        """Mixed approved/rejected findings both validate correctly in one pass."""
        fid1 = uuid4()
        fid2 = uuid4()
        approved = _make_finding(fid=fid1, original_value="45 days", proposed_value="30 days")
        rejected = _make_finding(fid=fid2, review_decision=ReviewDecision.REJECTED,
                                 original_value="36 months", proposed_value="24 months")

        original = "Pay within 45 days. Term is 36 months."
        mutated = "Pay within 30 days. Term is 36 months."

        cr_applied = _make_change_record(str(fid1), "applied", "45 days", "30 days")
        cr_applied.source_location = "document"  # match the section key
        cr_rejected = _make_change_record(str(fid2), "rejected", "36 months", "24 months")
        mutation_result = self._make_mutation_result(
            original, mutated, applied_changes=[cr_applied], rejected_changes=[cr_rejected]
        )

        result = self.engine.validate([approved, rejected], mutation_result)

        assert result.passed is True
        statuses = {r.finding_id: r.validation_status for r in result.finding_results}
        assert statuses[str(fid1)] == "passed"
        assert statuses[str(fid2)] == "passed"
