"""Post-Edit Validation Engine.

After approved edits are applied to the final document, this engine:
1. Verifies that approved violations were actually resolved.
2. Verifies that rejected findings remain unresolved (the problem persists).
3. Detects any unexpected mutations (accidental changes to non-targeted text).
4. Produces a per-finding validation result and an overall pass/fail verdict.

Validation is deterministic where possible (comparing against the proposed
values / original values in findings) and does NOT re-invoke the LLM.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.persistence.models.finding import Finding
    from app.services.mutation_service import ChangeRecord, MutationResult


@dataclass
class FindingValidationResult:
    """Validation result for a single finding."""
    finding_id: str
    reviewer_decision: str  # approved / rejected / pending
    application_status: str  # applied / rejected / failed
    validation_status: str   # passed / failed / skipped
    reason: str
    original_value: str | None
    proposed_value: str | None
    value_in_final_doc: str | None  # what we found at the relevant position


@dataclass
class PostEditValidationResult:
    """Overall result of post-edit validation."""
    passed: bool
    summary: str
    finding_results: list[FindingValidationResult] = field(default_factory=list)
    unexpected_changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "summary": self.summary,
            "finding_results": [
                {
                    "finding_id": r.finding_id,
                    "reviewer_decision": r.reviewer_decision,
                    "application_status": r.application_status,
                    "validation_status": r.validation_status,
                    "reason": r.reason,
                    "original_value": r.original_value,
                    "proposed_value": r.proposed_value,
                    "value_in_final_doc": r.value_in_final_doc,
                }
                for r in self.finding_results
            ],
            "unexpected_changes": self.unexpected_changes,
        }


class PostEditValidationEngine:
    """Deterministic post-edit validation.

    Does NOT call the LLM. Validates by checking:
    - Approved + applied findings: proposed_value present in mutated text, original_value absent (if unique).
    - Rejected findings: original_value still present (the problem was not fixed).
    - Unexpected changes: sections whose hashes changed but that weren't targeted by any finding.
    """

    def validate(
        self,
        findings: list["Finding"],
        mutation_result: "MutationResult",
    ) -> PostEditValidationResult:
        """Run post-edit validation.

        Args:
            findings: All findings for the run.
            mutation_result: Result of the mutation engine.

        Returns:
            PostEditValidationResult with per-finding verdicts.
        """
        mutated_text = mutation_result.mutated_text
        finding_results: list[FindingValidationResult] = []
        all_passed = True

        from app.core.constants import ApplicationStatus, ReviewDecision, ValidationStatus

        # Build a lookup from finding_id → change record for quick access
        applied_ids = {cr.finding_id for cr in mutation_result.applied_changes}
        rejected_ids = {cr.finding_id for cr in mutation_result.rejected_changes}
        failed_ids = {cr.finding_id for cr in mutation_result.failed_changes}

        for finding in findings:
            fid = str(finding.id)
            original = finding.original_value
            proposed = finding.proposed_value

            decision = finding.review_decision.value if finding.review_decision else "pending"

            # --- Pending findings are out of scope for post-edit validation ---
            if finding.review_decision == ReviewDecision.PENDING:
                finding_results.append(FindingValidationResult(
                    finding_id=fid,
                    reviewer_decision=decision,
                    application_status="pending",
                    validation_status=ValidationStatus.SKIPPED.value,
                    reason="Finding not yet reviewed; skipped.",
                    original_value=original,
                    proposed_value=proposed,
                    value_in_final_doc=None,
                ))
                continue

            # --- Rejected findings: original_value should STILL be in the document ---
            if finding.review_decision == ReviewDecision.REJECTED:
                if original is None:
                    # No specific value to check
                    status_val = ValidationStatus.SKIPPED.value
                    reason = "Rejected finding has no original_value to verify."
                elif original in mutated_text:
                    status_val = ValidationStatus.PASSED.value
                    reason = f"Correctly preserved: '{original}' still present in final document."
                else:
                    status_val = ValidationStatus.FAILED.value
                    all_passed = False
                    reason = (
                        f"Unexpected: '{original}' not found in final document even though "
                        "this finding was rejected (reviewer did not approve changing it)."
                    )

                finding_results.append(FindingValidationResult(
                    finding_id=fid,
                    reviewer_decision=decision,
                    application_status="rejected",
                    validation_status=status_val,
                    reason=reason,
                    original_value=original,
                    proposed_value=proposed,
                    value_in_final_doc=original if (original and original in mutated_text) else None,
                ))
                continue

            # --- Approved findings: proposed_value should be in the document ---
            if finding.review_decision == ReviewDecision.APPROVED:
                if fid in failed_ids:
                    # Application failed – this is a hard failure
                    all_passed = False
                    finding_results.append(FindingValidationResult(
                        finding_id=fid,
                        reviewer_decision=decision,
                        application_status="failed",
                        validation_status=ValidationStatus.FAILED.value,
                        reason=f"Edit application failed. '{original}' was not found in document during mutation.",
                        original_value=original,
                        proposed_value=proposed,
                        value_in_final_doc=None,
                    ))
                    continue

                if original is None and proposed is None:
                    # No specific text change – approval noted, nothing to verify
                    finding_results.append(FindingValidationResult(
                        finding_id=fid,
                        reviewer_decision=decision,
                        application_status="applied",
                        validation_status=ValidationStatus.PASSED.value,
                        reason="Finding approved with no text substitution; no textual verification needed.",
                        original_value=None,
                        proposed_value=None,
                        value_in_final_doc=None,
                    ))
                    continue

                # Check that proposed_value is now in the document
                proposed_present = proposed and (proposed in mutated_text)
                original_absent = original and (original not in mutated_text)

                if proposed_present and original_absent:
                    status_val = ValidationStatus.PASSED.value
                    reason = (
                        f"Approved edit applied correctly: '{proposed}' present in final document, "
                        f"'{original}' no longer present."
                    )
                elif proposed_present and not original_absent:
                    # Both present – possibly ambiguous match (multiple occurrences)
                    status_val = ValidationStatus.PASSED.value
                    reason = (
                        f"Approved edit applied (proposed_value present). Note: original_value also still "
                        f"present elsewhere (multiple occurrences). First occurrence substituted."
                    )
                elif not proposed_present:
                    status_val = ValidationStatus.FAILED.value
                    all_passed = False
                    reason = (
                        f"Proposed value '{proposed}' NOT found in final document. "
                        f"Edit may not have been applied correctly."
                    )
                else:
                    status_val = ValidationStatus.PASSED.value
                    reason = "Verification inconclusive (no specific values to check)."

                finding_results.append(FindingValidationResult(
                    finding_id=fid,
                    reviewer_decision=decision,
                    application_status="applied" if fid in applied_ids else "pending",
                    validation_status=status_val,
                    reason=reason,
                    original_value=original,
                    proposed_value=proposed,
                    value_in_final_doc=proposed if proposed_present else None,
                ))

        # --- Detect unexpected section changes ---
        unexpected: list[str] = []
        targeted_sections: set[str] = set()
        # A section is "targeted" if any applied change's source_location mentions it,
        # or if the section text before/after contains the mutated values.
        for cr in mutation_result.applied_changes:
            if cr.source_location:
                targeted_sections.add(cr.source_location.lower())
            if cr.original_value or cr.new_value:
                # Find which section in before/after hashes contains this original/new value
                for s_name, s_before in mutation_result.section_hashes_before.items():
                    if s_name == "_full_document":
                        continue
                    t_before = s_before.get("text", "")
                    if (cr.original_value and cr.original_value in t_before) or (cr.new_value and cr.new_value in t_before):
                        targeted_sections.add(s_name.lower())
                for s_name, s_after in mutation_result.section_hashes_after.items():
                    if s_name == "_full_document":
                        continue
                    t_after = s_after.get("text", "")
                    if (cr.original_value and cr.original_value in t_after) or (cr.new_value and cr.new_value in t_after):
                        targeted_sections.add(s_name.lower())

        hash_comparison = mutation_result.hash_comparison
        for section_name, hashes in hash_comparison.items():
            if section_name == "_full_document":
                continue
            if hashes.get("changed", False):
                section_lower = section_name.lower()
                if not any(ts in section_lower or section_lower in ts for ts in targeted_sections):
                    unexpected.append(
                        f"Section '{section_name}' changed unexpectedly "
                        f"(before_hash: {hashes.get('before_hash', '')[:12]}..., "
                        f"after_hash: {hashes.get('after_hash', '')[:12]}...)"
                    )

        # Build summary
        n_applied = len(mutation_result.applied_changes)
        n_rejected = len(mutation_result.rejected_changes)
        n_failed = len(mutation_result.failed_changes)
        n_passed_findings = sum(1 for r in finding_results if r.validation_status == "passed")
        n_failed_findings = sum(1 for r in finding_results if r.validation_status == "failed")

        if unexpected:
            all_passed = False

        summary_parts = [
            f"{n_applied} change(s) applied",
            f"{n_rejected} rejected",
            f"{n_failed} failed",
            f"{n_passed_findings} validation check(s) passed",
        ]
        if n_failed_findings:
            summary_parts.append(f"{n_failed_findings} validation check(s) FAILED")
        if unexpected:
            summary_parts.append(f"{len(unexpected)} unexpected section change(s) detected")

        summary = ". ".join(summary_parts) + "."

        return PostEditValidationResult(
            passed=all_passed,
            summary=summary,
            finding_results=finding_results,
            unexpected_changes=unexpected,
        )
