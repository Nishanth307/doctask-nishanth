"""Integration test for Zenith Contract Document Mutation and Verification Lifecycle.

Validates the complete workflow requirements:
1. Contradictions without policy resolution remain without proposed substitutions.
2. Approved policy violations with concrete proposed edits surgically modify the document text.
3. Rejected findings leave the original document text untouched.
4. Section SHA-256 hashes change ONLY for modified sections and remain identical for untouched sections.
5. Findings without concrete edits are marked NOT_APPLICABLE, NEVER 'applied'.
6. Running mutation twice is strictly idempotent.
"""
from uuid import uuid4
from app.core.constants import ApplicationStatus, FindingSeverity, ReviewDecision
from app.persistence.models.finding import Finding
from app.services.mutation_service import DocumentMutationEngine, compute_section_hashes


ZENITH_CONTRACT_TEXT = """ZENITH SERVICES AGREEMENT

This Agreement is entered into by and between Zenith Corp ("Company") and Acme Services ("Provider").

1. Term of Agreement
The initial term of this Agreement is 36 months, commencing on the Effective Date.

2. Payment Terms
Invoices are payable within 45 days of receipt by Company. Late payments shall accrue interest at 1.5% per month.

3. Termination
Either party may terminate this Agreement without cause upon providing 90 days prior written notice.

4. Governing Law and Jurisdiction
This Agreement shall be governed by the laws of Karnataka, India.

5. Insurance
Provider shall maintain commercial general liability insurance with limits not less than $2,000,000 per occurrence.

6. Miscellaneous
This Agreement constitutes the entire agreement between the parties.
"""


def test_zenith_surgical_mutation_and_section_hashes():
    engine = DocumentMutationEngine()
    run_id = str(uuid4())

    # 1. Approved: Initial Term 36 months -> 24 months
    f1 = Finding(
        id=uuid4(),
        run_id=uuid4(),
        title="Initial Term Exceeds Cap",
        description="Term is 36 months, exceeding policy maximum of 24 months.",
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.APPROVED,
        original_value="36 months",
        proposed_value="24 months",
        proposed_edit="36 months → 24 months",
    )

    # 2. Approved: Termination Notice 90 days -> 60 days
    f2 = Finding(
        id=uuid4(),
        run_id=uuid4(),
        title="Termination Notice Exceeds Standard",
        description="Notice is 90 days, exceeding the policy limit of 60 days.",
        severity=FindingSeverity.WARNING,
        review_decision=ReviewDecision.APPROVED,
        original_value="90 days",
        proposed_value="60 days",
        proposed_edit="90 days → 60 days",
    )

    # 3. Rejected: Payment terms 45 days -> 30 days (User rejects edit, preserving 45 days)
    f3 = Finding(
        id=uuid4(),
        run_id=uuid4(),
        title="Payment Due Period Policy Violation",
        description="Payment due is 45 days, exceeding policy maximum of 30 days.",
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.REJECTED,
        original_value="45 days",
        proposed_value="30 days",
        proposed_edit="45 days → 30 days",
    )

    # 4. Raw Contradiction: No proposed substitution
    f4 = Finding(
        id=uuid4(),
        run_id=uuid4(),
        title="Conflicting Insurance Coverage",
        description="Conflicting values found for insurance coverage. No policy dictates winner.",
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.APPROVED,
        original_value="$2,000,000",
        proposed_value=None,  # No proposed edit!
        proposed_edit=None,
    )

    result = engine.apply_approved_edits(
        source_text=ZENITH_CONTRACT_TEXT,
        findings=[f1, f2, f3, f4],
        run_id=run_id,
    )

    # Invariants verification:
    # 1. 36 months was mutated to 24 months
    assert "24 months" in result.mutated_text
    assert "36 months" not in result.mutated_text

    # 2. 90 days was mutated to 60 days
    assert "60 days" in result.mutated_text
    assert "90 days" not in result.mutated_text

    # 3. 45 days was REJECTED, so it remains unchanged!
    assert "45 days" in result.mutated_text
    assert "30 days" not in result.mutated_text

    # 4. Insurance $2,000,000 remains untouched
    assert "$2,000,000" in result.mutated_text

    # 5. Applied changes count
    assert len(result.applied_changes) == 2
    applied_findings = {cr.original_value for cr in result.applied_changes}
    assert applied_findings == {"36 months", "90 days"}

    # 6. Rejected changes count
    assert len(result.rejected_changes) == 1
    assert result.rejected_changes[0].original_value == "45 days"
    assert result.rejected_changes[0].application_status == "rejected"

    # 7. Finding without proposed edit is marked NOT_APPLICABLE (in failed_changes)
    assert len(result.failed_changes) == 1
    assert result.failed_changes[0].application_status == "not_applicable"
    assert result.failed_changes[0].original_value == "$2,000,000"

    # 8. Section Hashes proof
    hashes = result.hash_comparison
    # Term was changed
    assert hashes["term_renewal"]["changed"] is True
    # Termination was changed
    assert hashes["termination"]["changed"] is True
    # Payment terms was rejected (untouched) -> changed must be False!
    assert hashes["payment_terms"]["changed"] is False
    # Governing law was untouched -> changed must be False!
    assert hashes["governing_law"]["changed"] is False

    # 9. Idempotency test: Re-running mutation on mutated_text produces same output
    idempotent_result = engine.apply_approved_edits(
        source_text=result.mutated_text,
        findings=[f1, f2, f3, f4],
        run_id=run_id,
    )
    assert idempotent_result.mutated_text == result.mutated_text
    # On second pass, f1 and f2 are detected as already applied (idempotent no-op)
    assert len(idempotent_result.applied_changes) == 2
    for cr in idempotent_result.applied_changes:
        assert "Edit already applied" in cr.reason
