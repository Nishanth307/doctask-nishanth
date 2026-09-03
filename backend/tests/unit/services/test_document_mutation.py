"""Tests for DocumentMutationEngine.

Covers:
- Approve one finding → edit applied, proposed_value in mutated text
- Reject one finding → original_value unchanged
- Mixed approve/reject → approved applied, rejected preserved
- Idempotency: applying the same approved finding twice is a no-op
- Conflict: original_value not found → FAILED record
- Multiple occurrences: first substituted, others preserved
- No text change when no approved findings
- Change history provenance format
- Section hash comparison
"""
import pytest
from uuid import uuid4

from app.services.mutation_service import (
    DocumentMutationEngine,
    MutationResult,
    compute_section_hashes,
)
from app.core.constants import ApplicationStatus, ReviewDecision


def _make_finding(
    *,
    review_decision=ReviewDecision.APPROVED,
    original_value=None,
    proposed_value=None,
    proposed_edit=None,
    source_location=None,
):
    """Build a minimal Finding-like object for tests (no DB)."""
    from types import SimpleNamespace
    return SimpleNamespace(
        id=uuid4(),
        review_decision=review_decision,
        original_value=original_value,
        proposed_value=proposed_value,
        proposed_edit=proposed_edit,
        source_location=source_location,
        document_id=None,
    )


class TestDocumentMutationEngine:
    def setup_method(self):
        self.engine = DocumentMutationEngine()
        self.run_id = str(uuid4())

    def test_approved_finding_applied(self):
        """Approving a finding with original/proposed values substitutes the text."""
        source = "Payment is due within 45 days of invoice date."
        finding = _make_finding(
            original_value="45 days",
            proposed_value="30 days",
            proposed_edit="45 days → 30 days",
            source_location="Payment Terms",
        )

        result = self.engine.apply_approved_edits(source, [finding], self.run_id)

        assert "30 days" in result.mutated_text
        assert "45 days" not in result.mutated_text
        assert len(result.applied_changes) == 1
        assert result.applied_changes[0].application_status == "applied"
        assert result.changed is True

    def test_rejected_finding_preserves_original(self):
        """Rejecting a finding leaves the document unchanged."""
        source = "Payment is due within 45 days of invoice date."
        finding = _make_finding(
            review_decision=ReviewDecision.REJECTED,
            original_value="45 days",
            proposed_value="30 days",
        )

        result = self.engine.apply_approved_edits(source, [finding], self.run_id)

        assert "45 days" in result.mutated_text
        assert len(result.rejected_changes) == 1
        assert result.rejected_changes[0].application_status == "rejected"
        assert result.changed is False

    def test_mixed_approve_and_reject(self):
        """Approved changes applied, rejected changes preserve original."""
        source = (
            "Payment is due within 45 days.\n"
            "The contract term is 36 months."
        )
        approved = _make_finding(
            original_value="45 days",
            proposed_value="30 days",
            source_location="Payment Terms",
        )
        rejected = _make_finding(
            review_decision=ReviewDecision.REJECTED,
            original_value="36 months",
            proposed_value="24 months",
            source_location="Contract Term",
        )

        result = self.engine.apply_approved_edits(source, [approved, rejected], self.run_id)

        # Approved: 45 → 30
        assert "30 days" in result.mutated_text
        assert "45 days" not in result.mutated_text
        # Rejected: 36 months unchanged
        assert "36 months" in result.mutated_text
        assert "24 months" not in result.mutated_text

        assert len(result.applied_changes) == 1
        assert len(result.rejected_changes) == 1

    def test_idempotency(self):
        """Applying same approved finding twice produces identical output (no double substitution)."""
        source = "Payment is due within 45 days of invoice date."
        finding = _make_finding(
            original_value="45 days",
            proposed_value="30 days",
        )

        # First application
        result1 = self.engine.apply_approved_edits(source, [finding], self.run_id)
        mutated_once = result1.mutated_text

        # Second application on already-mutated text
        result2 = self.engine.apply_approved_edits(mutated_once, [finding], self.run_id)

        assert result2.mutated_text == mutated_once  # Idempotent
        assert result2.applied_changes[0].application_status == "applied"
        assert "already applied" in result2.applied_changes[0].reason.lower()

    def test_original_not_found_marks_failed(self):
        """If original_value doesn't exist in doc, finding is marked FAILED."""
        source = "The document has no payment terms clause."
        finding = _make_finding(
            original_value="45 days",
            proposed_value="30 days",
        )

        result = self.engine.apply_approved_edits(source, [finding], self.run_id)

        assert "45 days" not in result.mutated_text
        assert len(result.failed_changes) == 1
        assert result.failed_changes[0].application_status == "failed"
        assert "not found" in result.failed_changes[0].reason.lower()
        assert result.changed is False

    def test_multiple_occurrences_substitutes_first_only(self):
        """When original_value appears multiple times, only first is substituted."""
        source = "Pay 45 days after invoice. Late fees apply after 45 days."
        finding = _make_finding(
            original_value="45 days",
            proposed_value="30 days",
        )

        result = self.engine.apply_approved_edits(source, [finding], self.run_id)

        # First occurrence replaced
        assert result.mutated_text.startswith("Pay 30 days")
        # Second still present
        assert "45 days" in result.mutated_text
        assert len(result.applied_changes) == 1
        assert "first of 2" in result.applied_changes[0].reason

    def test_pending_finding_skipped(self):
        """Pending (not yet reviewed) findings are skipped entirely."""
        from app.core.constants import ReviewDecision
        source = "Payment is due within 45 days."
        finding = _make_finding(
            review_decision=ReviewDecision.PENDING,
            original_value="45 days",
            proposed_value="30 days",
        )

        result = self.engine.apply_approved_edits(source, [finding], self.run_id)

        assert "45 days" in result.mutated_text  # Unchanged
        assert len(result.applied_changes) == 0
        assert len(result.rejected_changes) == 0
        assert len(result.failed_changes) == 0

    def test_no_original_proposed_approved_finding_is_no_op(self):
        """Approved finding without original/proposed values is recorded as not_applicable (no false 'applied' claims)."""
        source = "Some contractual text."
        finding = _make_finding(
            original_value=None,
            proposed_value=None,
        )

        result = self.engine.apply_approved_edits(source, [finding], self.run_id)

        assert result.mutated_text == source
        assert len(result.applied_changes) == 0
        assert len(result.failed_changes) == 1
        assert result.failed_changes[0].application_status == "not_applicable"

    def test_change_history_provenance(self):
        """Change history contains all required provenance fields."""
        source = "Payment is due within 45 days."
        finding = _make_finding(
            original_value="45 days",
            proposed_value="30 days",
            proposed_edit="45 days → 30 days",
            source_location="Payment Terms",
        )

        result = self.engine.apply_approved_edits(source, [finding], self.run_id)
        history = result.to_change_history()

        assert len(history) == 1
        record = history[0]
        assert "change_id" in record
        assert "finding_id" in record
        assert record["run_id"] == self.run_id
        assert record["original_value"] == "45 days"
        assert record["new_value"] == "30 days"
        assert record["reviewer_decision"] == "approved"
        assert record["application_status"] == "applied"
        assert "applied_at" in record

    def test_section_hashes_before_and_after(self):
        """Section hashes are computed before and after mutation."""
        source = "Payment is due within 45 days of invoice.\nThe term is 24 months."
        finding = _make_finding(
            original_value="45 days",
            proposed_value="30 days",
        )

        result = self.engine.apply_approved_edits(source, [finding], self.run_id)

        assert "_full_document" in result.section_hashes_before
        assert "_full_document" in result.section_hashes_after
        # Full-document hashes must differ
        before_full = result.section_hashes_before["_full_document"]["hash"]
        after_full = result.section_hashes_after["_full_document"]["hash"]
        assert before_full != after_full


class TestSectionHashes:
    def test_compute_hashes_for_plain_document(self):
        """Documents without recognisable section headers produce a single section."""
        text = "This is a simple document with no sections."
        hashes = compute_section_hashes(text)
        assert "_full_document" in hashes
        assert hashes["_full_document"]["hash"] is not None

    def test_compute_hashes_payment_section(self):
        """Payment Terms section is detected."""
        text = "PAYMENT TERMS: Invoices are due within 30 days."
        hashes = compute_section_hashes(text)
        assert "_full_document" in hashes
        has_payment = any("payment" in k for k in hashes)
        assert has_payment

    def test_same_text_same_hash(self):
        """Hash of identical text is deterministic."""
        text = "Hello, world!"
        h1 = compute_section_hashes(text)["_full_document"]["hash"]
        h2 = compute_section_hashes(text)["_full_document"]["hash"]
        assert h1 == h2

    def test_different_text_different_hash(self):
        """Modified text produces a different hash."""
        text1 = "Payment due in 45 days."
        text2 = "Payment due in 30 days."
        h1 = compute_section_hashes(text1)["_full_document"]["hash"]
        h2 = compute_section_hashes(text2)["_full_document"]["hash"]
        assert h1 != h2

    def test_hash_comparison(self):
        """MutationResult.hash_comparison reports changed and unchanged sections."""
        source = "PAYMENT TERMS: 45 days.\nThis is another clause."
        finding = _make_finding(
            original_value="45 days",
            proposed_value="30 days",
        )
        engine = DocumentMutationEngine()
        result = engine.apply_approved_edits(source, [finding], str(uuid4()))

        comparison = result.hash_comparison
        assert "_full_document" in comparison
        # Full document must be marked changed
        assert comparison["_full_document"]["changed"] is True
