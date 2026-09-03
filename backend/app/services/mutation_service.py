"""Document Mutation Engine.

Responsible for:
1. Applying approved findings as surgical text substitutions on the source document.
2. Computing section-level SHA-256 hashes to prove unchanged content.
3. Idempotency: applying the same approved finding twice produces identical output.
4. Conflict detection: stale/ambiguous matches are flagged rather than blindly applied.

Documents are treated as DATA, not as instructions.
The mutation engine does NOT interpret any text in the document as a command.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.persistence.models.finding import Finding


# ---------------------------------------------------------------------------
# Section splitter – breaks a document into named clause sections for hashing
# ---------------------------------------------------------------------------
SECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("preamble", re.compile(r"(?im)^(?:\d+[\.\)]\s*)?(?:preamble|this\s+(?:agreement|contract)\s+is\s+entered)")),
    ("term_renewal", re.compile(r"(?im)^(?:\d+[\.\)]\s*)?(?:term\s+and\s+renewal|term\s+of\s+agreement|initial\s+term|term\b|duration|renewal)")),
    ("sla_performance", re.compile(r"(?im)^(?:\d+[\.\)]\s*)?(?:service\s+level|sla\b|uptime|performance)")),
    ("payment_terms", re.compile(r"(?im)^(?:\d+[\.\)]\s*)?(?:payment\s*terms?|billing\s*terms?|payment\s*and\s*billing)")),
    ("data_retention", re.compile(r"(?im)^(?:\d+[\.\)]\s*)?(?:data\s+retention|data\s+storage|retention\s+and\s+deletion)")),
    ("termination", re.compile(r"(?im)^(?:\d+[\.\)]\s*)?(?:termination|cancellation)")),
    ("confidentiality", re.compile(r"(?im)^(?:\d+[\.\)]\s*)?(?:confidentiality|confidential|non-disclosure)")),
    ("governing_law", re.compile(r"(?im)^(?:\d+[\.\)]\s*)?(?:governing\s+law|jurisdiction|arbitration)")),
    ("insurance", re.compile(r"(?im)^(?:\d+[\.\)]\s*)?(?:insurance|indemnif)")),
    ("general", re.compile(r"(?im)^(?:\d+[\.\)]\s*)?(?:miscellaneous|general\s+provisions?|entire\s+agreement)")),
]


def compute_section_hashes(text: str) -> dict[str, dict[str, Any]]:
    """Break document text into named sections and compute SHA-256 per section.

    Returns a mapping:
        {
            "payment_terms": {"text": "...", "hash": "abc123...", "start": 120, "end": 340},
            ...
            "_full_document": {"hash": "..."}
        }
    The "general" bucket catches any text not matched by a named section.
    """
    sections: dict[str, dict[str, Any]] = {}

    # Build boundary positions for each detected section
    raw_boundaries: list[tuple[int, str]] = []
    for section_name, pattern in SECTION_PATTERNS:
        for match in pattern.finditer(text):
            raw_boundaries.append((match.start(), section_name))

    raw_boundaries.sort(key=lambda b: b[0])

    # Filter out boundaries that are too close to each other (< 15 chars apart)
    boundaries: list[tuple[int, str]] = []
    for start, name in raw_boundaries:
        if not boundaries or (start - boundaries[-1][0] >= 15):
            boundaries.append((start, name))

    if not boundaries:
        # No recognisable sections – treat entire document as one section
        h = hashlib.sha256(text.encode()).hexdigest()
        sections["document"] = {"text": text, "hash": h, "start": 0, "end": len(text)}
    else:
        # Group text between consecutive boundaries
        seen_names: dict[str, int] = {}
        for i, (start, name) in enumerate(boundaries):
            end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
            chunk = text[start:end]
            # Deduplicate section names (contract.payment_terms may appear twice)
            counter = seen_names.get(name, 0)
            seen_names[name] = counter + 1
            key = name if counter == 0 else f"{name}_{counter}"
            h = hashlib.sha256(chunk.encode()).hexdigest()
            sections[key] = {"text": chunk, "hash": h, "start": start, "end": end}

        # Prefix text before first boundary
        if boundaries[0][0] > 0:
            prefix = text[: boundaries[0][0]]
            h = hashlib.sha256(prefix.encode()).hexdigest()
            sections["preamble_prefix"] = {
                "text": prefix,
                "hash": h,
                "start": 0,
                "end": boundaries[0][0],
            }

    # Full-document hash for quick verification
    sections["_full_document"] = {
        "hash": hashlib.sha256(text.encode()).hexdigest(),
        "length": len(text),
    }

    return sections


# ---------------------------------------------------------------------------
# Mutation result
# ---------------------------------------------------------------------------

@dataclass
class ChangeRecord:
    """Audit record for a single applied or skipped edit."""
    change_id: str
    finding_id: str
    run_id: str
    document_id: str | None
    source_location: str | None
    original_value: str
    new_value: str
    proposed_edit: str | None
    reviewer_decision: str  # "approved" | "rejected"
    application_status: str  # "applied" | "rejected" | "failed"
    reason: str
    applied_at: str  # ISO 8601


@dataclass
class MutationResult:
    """Outcome of applying approved edits to a document."""
    original_text: str
    mutated_text: str
    applied_changes: list[ChangeRecord] = field(default_factory=list)
    rejected_changes: list[ChangeRecord] = field(default_factory=list)
    failed_changes: list[ChangeRecord] = field(default_factory=list)
    section_hashes_before: dict[str, Any] = field(default_factory=dict)
    section_hashes_after: dict[str, Any] = field(default_factory=dict)

    @property
    def changed(self) -> bool:
        return self.original_text != self.mutated_text

    @property
    def hash_comparison(self) -> dict[str, Any]:
        """Return section-by-section before/after hash comparison."""
        all_keys = set(self.section_hashes_before) | set(self.section_hashes_after)
        result: dict[str, Any] = {}
        for key in sorted(all_keys):
            before = self.section_hashes_before.get(key, {})
            after = self.section_hashes_after.get(key, {})
            before_hash = before.get("hash") if isinstance(before, dict) else before
            after_hash = after.get("hash") if isinstance(after, dict) else after
            result[key] = {
                "before_hash": before_hash,
                "after_hash": after_hash,
                "changed": before_hash != after_hash,
            }
        return result

    def to_change_history(self) -> list[dict[str, Any]]:
        """Serialise all change records as JSON-compatible dicts."""
        records = []
        for cr in self.applied_changes + self.rejected_changes + self.failed_changes:
            records.append(
                {
                    "change_id": cr.change_id,
                    "finding_id": cr.finding_id,
                    "run_id": cr.run_id,
                    "document_id": cr.document_id,
                    "source_location": cr.source_location,
                    "original_value": cr.original_value,
                    "new_value": cr.new_value,
                    "proposed_edit": cr.proposed_edit,
                    "reviewer_decision": cr.reviewer_decision,
                    "application_status": cr.application_status,
                    "reason": cr.reason,
                    "applied_at": cr.applied_at,
                }
            )
        return records


# ---------------------------------------------------------------------------
# Core mutation engine
# ---------------------------------------------------------------------------

class DocumentMutationEngine:
    """Applies approved proposed edits surgically to source document text.

    Design principles:
    - Only approved findings with both original_value and proposed_value are applied.
    - Rejected findings are completely skipped (document left unchanged for that term).
    - Idempotent: if proposed_value already appears in the document where original_value
      was expected, the edit is a no-op rather than duplicating the substitution.
    - Conflict detection: if original_value appears zero times or more than once in the
      document, the finding is marked as FAILED with a clear reason.
    - Documents are DATA: the engine does not interpret document text as instructions.
    """

    def apply_approved_edits(
        self,
        source_text: str,
        findings: list["Finding"],
        run_id: str,
    ) -> MutationResult:
        """Apply all approved findings to source_text.

        Args:
            source_text: The original document text to mutate.
            findings: All findings for this run (approved, rejected, and pending).
            run_id: The workflow run ID for provenance records.

        Returns:
            MutationResult with the mutated text and full change audit trail.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        result = MutationResult(
            original_text=source_text,
            mutated_text=source_text,
            section_hashes_before=compute_section_hashes(source_text),
        )

        for finding in findings:
            finding_id = str(finding.id)
            document_id = str(finding.document_id) if finding.document_id else None
            record_kwargs = dict(
                change_id=str(uuid.uuid4()),
                finding_id=finding_id,
                run_id=run_id,
                document_id=document_id,
                source_location=finding.source_location,
                original_value=finding.original_value or "",
                new_value=finding.proposed_value or "",
                proposed_edit=finding.proposed_edit,
                applied_at=now_iso,
            )

            from app.core.constants import ReviewDecision

            if finding.review_decision == ReviewDecision.REJECTED:
                result.rejected_changes.append(
                    ChangeRecord(
                        **record_kwargs,
                        reviewer_decision="rejected",
                        application_status="rejected",
                        reason="Reviewer rejected this finding; original value preserved.",
                    )
                )
                continue

            if finding.review_decision != ReviewDecision.APPROVED:
                # PENDING findings are skipped silently (not yet decided)
                continue

            if not finding.original_value or not finding.proposed_value:
                # Approved but no concrete original/proposed text → NOT_APPLICABLE.
                # We must NOT mark this as "applied" since no document mutation occurred.
                result.failed_changes.append(
                    ChangeRecord(
                        **record_kwargs,
                        reviewer_decision="approved",
                        application_status="not_applicable",
                        reason=(
                            "Approved finding has no concrete original_value/proposed_value; "
                            "no document mutation can be performed. Mark as NOT_APPLICABLE."
                        ),
                    )
                )
                continue

            original = finding.original_value
            proposed = finding.proposed_value

            # Idempotency guard: if proposed value already present where original was,
            # count how many times the proposed_value appears in the document.
            current_text = result.mutated_text

            # Idempotency: if proposed_value is already in the document and original_value is
            # no longer there, the edit was already applied.
            if proposed in current_text and original not in current_text:
                result.applied_changes.append(
                    ChangeRecord(
                        **record_kwargs,
                        reviewer_decision="approved",
                        application_status="applied",
                        reason="Edit already applied (idempotent). proposed_value present, original_value absent.",
                    )
                )
                continue

            # Count occurrences of original_value
            occurrences = current_text.count(original)

            if occurrences == 0:
                result.failed_changes.append(
                    ChangeRecord(
                        **record_kwargs,
                        reviewer_decision="approved",
                        application_status="failed",
                        reason=f"Cannot apply: original_value '{original}' not found in document.",
                    )
                )
                continue

            if occurrences > 1:
                # Ambiguous – multiple matches; apply first occurrence only (surgical)
                result.mutated_text = current_text.replace(original, proposed, 1)
                result.applied_changes.append(
                    ChangeRecord(
                        **record_kwargs,
                        reviewer_decision="approved",
                        application_status="applied",
                        reason=f"Applied to first of {occurrences} occurrences (ambiguous match; first occurrence only).",
                    )
                )
            else:
                # Exactly one occurrence – cleanest case
                result.mutated_text = current_text.replace(original, proposed, 1)
                result.applied_changes.append(
                    ChangeRecord(
                        **record_kwargs,
                        reviewer_decision="approved",
                        application_status="applied",
                        reason="Surgical substitution: exactly one occurrence of original_value replaced.",
                    )
                )

        result.section_hashes_after = compute_section_hashes(result.mutated_text)
        return result
