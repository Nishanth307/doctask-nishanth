"""FindingService: creates and syncs findings with canonical proposed-edit fields.

Every actionable finding must carry:
  - original_value: what the document currently says
  - proposed_value: what it should say after an approved edit
  - proposed_edit: human-readable "original → proposed"
  - source_location: where in the document the issue was found

This allows the DocumentMutationEngine to apply approved edits surgically.
"""
import re
from typing import Any
from uuid import UUID

from app.core.constants import FindingSeverity, ReviewDecision
from app.persistence.models.finding import Finding
from app.persistence.repositories.finding import FindingRepository
from app.workflow.conflicts import (
    build_contradiction_citation,
    build_contradiction_description,
)


def _extract_policy_edit(issue_text: str) -> tuple[str | None, str | None]:
    """Try to extract (original_value, proposed_value) from an examination issue string.

    The LLM tends to produce issues like:
      "Payment due period is 45 days, exceeding the maximum of 30 days."
      "Initial term is 36 months; policy requires no more than 24 months."

    We parse common patterns to build a proposed edit. If we can't parse it,
    we return (None, None) and the finding will have no specific text substitution.
    """
    # Common patterns for policy corrections
    patterns = [
        # "36 months, exceeding policy maximum of 24 months" or "exceeding ... 30 days"
        (
            r"(\d+(?:\.\d+)?)\s*(%|days?|months?|years?)\b.*?(?:maximum|max|should be|must be|no more than|at least|minimum|min|allowed|policy requires|policy limit|policy|limit(?:ed)? to)\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*(%|days?|months?|years?)",
            lambda m: (f"{m.group(1)}{m.group(2) if m.group(2) == '%' else ' ' + m.group(2)}", f"{m.group(3)}{m.group(4) if m.group(4) == '%' else ' ' + m.group(4)}"),
        ),
        # "Initial term is 36 months; policy requires 24 months"
        (
            r"(\d+(?:\.\d+)?)\s*(%|days?|months?|years?)[^.]*?(?:exceed|violat|too high|too long|above|longer than|below|policy requires|requires)\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*(%|days?|months?|years?)",
            lambda m: (f"{m.group(1)}{m.group(2) if m.group(2) == '%' else ' ' + m.group(2)}", f"{m.group(3)}{m.group(4) if m.group(4) == '%' else ' ' + m.group(4)}"),
        ),
        # "policy requires 24 months, currently 36 months"
        (
            r"policy[^.]*?(\d+(?:\.\d+)?)\s*(%|days?|months?|years?)[^.]*?(?:currently|is|was)\s*(\d+(?:\.\d+)?)\s*(%|days?|months?)",
            lambda m: (f"{m.group(3)}{m.group(4) if m.group(4) == '%' else ' ' + m.group(4)}", f"{m.group(1)}{m.group(2) if m.group(2) == '%' else ' ' + m.group(2)}"),
        ),
        # "change [from] 'X' to 'Y'" or "replace 'X' with 'Y'"
        (
            r"(?:change|replace|substitute|update)\s+(?:from\s+)?['\"]?([^'\"]+?)['\"]?\s+(?:to|with)\s+['\"]?([^'\"]+?)['\"]?(?:\.|$)",
            lambda m: (m.group(1).strip(), m.group(2).strip()),
        ),
        # "X -> Y" or "X → Y"
        (
            r"['\"]?([^'\"]+?)['\"]?\s*(?:->|→)\s*['\"]?([^'\"]+?)['\"]?(?:\.|$)",
            lambda m: (m.group(1).strip(), m.group(2).strip()),
        ),
    ]

    issue_lower = issue_text.lower()
    for pattern_str, extractor in patterns:
        m = re.search(pattern_str, issue_lower)
        if m:
            try:
                orig, prop = extractor(m)
                if orig and prop and orig.strip() != prop.strip():
                    return orig.strip(), prop.strip()
            except Exception:
                pass
    return None, None


class FindingService:
    def __init__(self, repository: FindingRepository) -> None:
        self.repository = repository

    def sync_contradiction_findings(
        self,
        run_id: UUID,
        contradictions: list[dict[str, Any]],
    ) -> None:
        existing_findings = self.repository.get_by_run_id(run_id)

        existing_contradictions = {}
        for f in existing_findings:
            meta = f.finding_metadata or {}
            if meta.get("type") == "contradiction" and "semantic_key" in meta:
                existing_contradictions[meta["semantic_key"]] = f

        active_keys = set()
        for contradiction in contradictions:
            semantic_key = contradiction.get("semantic_key")
            if not semantic_key:
                continue

            active_keys.add(semantic_key)
            field = contradiction.get("field", "unknown field")
            title = f"Conflicting {field}"
            description = build_contradiction_description(contradiction)
            citation = build_contradiction_citation(contradiction)

            # For contradictions without a policy rule resolving them, neither document
            # is authoritative. Do NOT fabricate an arbitrary proposed replacement.
            # Record original_value as the first document's value, leave proposed_value None,
            # and set review_decision to NEEDS_RESOLUTION.
            values = contradiction.get("values", [])
            original_value = None
            source_location = None
            document_id = None

            if len(values) >= 2:
                original_value = values[0].get("value")
                source_location = values[0].get("source_text", "")[:200] if values[0].get("source_text") else None

            # Strictly no automated proposed_value or proposed_edit for raw contradictions
            proposed_value = None
            proposed_edit = None

            if semantic_key in existing_contradictions:
                f_existing = existing_contradictions[semantic_key]
                if f_existing.review_decision == ReviewDecision.PENDING:
                    f_existing.title = title
                    f_existing.description = description
                    f_existing.citation = citation
                    f_existing.finding_metadata = {
                        "type": "contradiction",
                        "semantic_key": semantic_key,
                        "field": field,
                        "needs_resolution": True,
                    }
                    if original_value:
                        f_existing.original_value = original_value
                    f_existing.proposed_value = None
                    f_existing.proposed_edit = None
                    if source_location:
                        f_existing.source_location = source_location
            else:
                from app.workflow.conflicts import contradiction_to_finding
                new_finding = contradiction_to_finding(run_id, contradiction)
                new_finding.review_decision = ReviewDecision.PENDING
                new_finding.original_value = original_value
                new_finding.proposed_value = None
                new_finding.proposed_edit = None
                new_finding.source_location = source_location
                new_finding.finding_metadata = {
                    "type": "contradiction",
                    "semantic_key": semantic_key,
                    "field": field,
                    "needs_resolution": True,
                }
                self.repository.create(new_finding)

        # Clean up stale pending contradictions
        for key, f in existing_contradictions.items():
            if key not in active_keys and f.review_decision == ReviewDecision.PENDING:
                self.repository.delete(f)

        self.repository.db.flush()

    def sync_checklist_findings(
        self,
        run_id: UUID,
        issues: list[str],
    ) -> None:
        existing_findings = self.repository.get_by_run_id(run_id)

        contradiction_descriptions = {
            f.description for f in existing_findings
            if (f.finding_metadata or {}).get("type") == "contradiction"
        }

        existing_violations = {}
        for f in existing_findings:
            meta = f.finding_metadata or {}
            if meta.get("type") == "violation":
                existing_violations[f.description] = f

        active_issues = set()
        for issue_text in issues:
            if not issue_text.strip():
                continue

            if issue_text in contradiction_descriptions or "Conflicting values were found for" in issue_text:
                continue

            active_issues.add(issue_text)

            if issue_text not in existing_violations:
                new_finding = Finding(
                    run_id=run_id,
                    title="Policy Violation",
                    description=issue_text,
                    severity=FindingSeverity.ERROR,
                    review_decision=ReviewDecision.PENDING,
                    citation=None,
                    original_value=None,
                    proposed_value=None,
                    proposed_edit=None,
                    finding_metadata={
                        "type": "violation",
                    },
                )
                self.repository.create(new_finding)

        # Clean up stale pending violations
        for issue_text, f in existing_violations.items():
            if issue_text not in active_issues and f.review_decision == ReviewDecision.PENDING:
                self.repository.delete(f)

        self.repository.db.flush()
