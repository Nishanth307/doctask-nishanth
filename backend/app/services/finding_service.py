from typing import Any
from uuid import UUID

from app.core.constants import FindingSeverity, ReviewDecision
from app.persistence.models.finding import Finding
from app.persistence.repositories.finding import FindingRepository
from app.workflow.conflicts import (
    build_contradiction_citation,
    build_contradiction_description,
)


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

            if semantic_key in existing_contradictions:
                f = existing_contradictions[semantic_key]
                if f.review_decision == ReviewDecision.PENDING:
                    f.title = title
                    f.description = description
                    f.citation = citation
                    # base repository registers with session, flush happens at caller or db.commit()
            else:
                new_finding = Finding(
                    run_id=run_id,
                    title=title,
                    description=description,
                    severity=FindingSeverity.ERROR,
                    review_decision=ReviewDecision.PENDING,
                    citation=citation,
                    finding_metadata={
                        "type": "contradiction",
                        "semantic_key": semantic_key,
                        "field": field,
                    },
                )
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

        existing_violations = {}
        for f in existing_findings:
            meta = f.finding_metadata or {}
            if meta.get("type") == "violation":
                existing_violations[f.description] = f

        active_issues = set()
        for issue_text in issues:
            if not issue_text.strip():
                continue

            active_issues.add(issue_text)
            title = "Policy Violation"

            if issue_text not in existing_violations:
                new_finding = Finding(
                    run_id=run_id,
                    title=title,
                    description=issue_text,
                    severity=FindingSeverity.ERROR,
                    review_decision=ReviewDecision.PENDING,
                    citation=None,
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
