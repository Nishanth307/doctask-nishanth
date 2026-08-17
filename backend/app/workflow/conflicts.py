from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from app.core.constants import FindingSeverity, ReviewDecision
from app.persistence.models.finding import Finding


def normalize_semantic_key(value: str) -> str:
    return str(value).strip().lower()


def normalize_fact_value(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def detect_contradictions(
    facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    facts_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for fact in facts:
        semantic_key = normalize_semantic_key(
            fact.get("semantic_key", "")
        )
        value = normalize_fact_value(
            fact.get("value", "")
        )

        if not semantic_key or not value:
            continue

        facts_by_key[semantic_key].append(fact)

    contradictions = []

    for semantic_key, semantic_facts in facts_by_key.items():
        distinct_values = {
            normalize_fact_value(
                fact.get("value", "")
            )
            for fact in semantic_facts
        }

        if len(distinct_values) <= 1:
            continue

        distinct_documents = {
            fact.get("source_document") or fact.get("document_filename") or ""
            for fact in semantic_facts
        }

        if len(distinct_documents) <= 1:
            continue

        contradictions.append(
            {
                "semantic_key": semantic_key,
                "field": semantic_facts[0].get(
                    "field",
                    semantic_key,
                ),
                "values": semantic_facts,
            }
        )


    return contradictions


def build_contradiction_description(
    contradiction: dict[str, Any],
) -> str:
    field = contradiction.get(
        "field",
        contradiction.get("semantic_key", "unspecified field"),
    )
    return (
        f"Conflicting values were found for '{field}'. "
        f"No value was selected automatically."
    )


def build_contradiction_citation(
    contradiction: dict[str, Any],
) -> dict[str, Any]:
    values = contradiction.get("values", [])
    evidence = []
    for fact in values:
        evidence.append(
            {
                "document": fact.get("source_document") or fact.get("document_filename"),
                "value": fact.get("value"),
                "source_text": fact.get("source_text"),
                "confidence": fact.get("confidence"),
            }
        )
    return {
        "type": "contradiction",
        "semantic_key": contradiction.get("semantic_key"),
        "sources": evidence,
    }


def contradiction_to_finding(
    run_id: UUID,
    contradiction: dict[str, Any],
) -> Finding:
    values = contradiction.get("values", [])
    evidence = []

    for fact in values:
        evidence.append(
            {
                "document": fact.get("source_document") or fact.get("document_filename"),
                "value": fact.get("value"),
                "source_text": fact.get("source_text"),
                "confidence": fact.get("confidence"),
            }
        )

    field = contradiction.get(
        "field",
        contradiction.get("semantic_key", "unknown field"),
    )

    description = (
        f"Conflicting values were found for '{field}'. "
        f"No value was selected automatically."
    )

    return Finding(
        run_id=run_id,
        title=f"Conflicting {field}",
        description=description,
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.PENDING,
        citation={
            "type": "contradiction",
            "semantic_key": contradiction.get("semantic_key"),
            "sources": evidence,
        },
        finding_metadata={
            "type": "contradiction",
            "semantic_key": contradiction.get("semantic_key"),
        },
    )


def build_contradiction_examination(
    contradictions: list[dict[str, Any]],
):
    from app.llm.schemas import ExaminationResult

    issues = [
        build_contradiction_description(contradiction)
        for contradiction in contradictions
    ]

    count = len(contradictions)
    summary = (
        f"Found {count} unresolved contradiction(s) across source documents. "
        "The corpus cannot be treated as consistent until these conflicts are reviewed."
    )

    return ExaminationResult(
        is_valid=False,
        confidence=1.0,
        issues=issues,
        summary=summary,
    )

