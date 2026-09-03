"""Validate Edits workflow node.

After edits are applied, this node:
1. Runs the PostEditValidationEngine against the mutated document.
2. Updates each finding's validation_status in the database.
3. Stores the validation result in state.
"""
from __future__ import annotations

from app.workflow.state import WorkflowState


class ValidateEditsNode:
    """Run post-edit validation against the final mutated document."""

    def __call__(self, state: WorkflowState) -> WorkflowState:
        run_id = state.get("run_id")
        final_text = state.get("final_document_text", "")

        if not run_id:
            return {**state, "error": "run_id missing in state", "status": "failed"}

        from app.core.database import SessionLocal
        from app.core.constants import ValidationStatus
        from app.persistence.models.finding import Finding
        from app.services.mutation_service import DocumentMutationEngine, MutationResult
        from app.services.validation_service import PostEditValidationEngine

        db = SessionLocal()
        try:
            findings = db.query(Finding).filter(Finding.run_id == run_id).all()

            # Reconstruct a minimal MutationResult for the validator
            # (applied_changes list comes from state)
            from app.services.mutation_service import ChangeRecord, MutationResult, compute_section_hashes

            # Rebuild applied/rejected change records from state
            applied_changes = []
            rejected_changes = []
            for record in state.get("applied_changes", []):
                cr = ChangeRecord(
                    change_id=record.get("change_id", ""),
                    finding_id=record.get("finding_id", ""),
                    run_id=record.get("run_id", ""),
                    document_id=record.get("document_id"),
                    source_location=record.get("source_location"),
                    original_value=record.get("original_value", ""),
                    new_value=record.get("new_value", ""),
                    proposed_edit=record.get("proposed_edit"),
                    reviewer_decision=record.get("reviewer_decision", ""),
                    application_status=record.get("application_status", ""),
                    reason=record.get("reason", ""),
                    applied_at=record.get("applied_at", ""),
                )
                if cr.application_status == "applied":
                    applied_changes.append(cr)
                elif cr.application_status == "rejected":
                    rejected_changes.append(cr)

            # Get original text from documents in state
            documents = state.get("documents", [])
            original_text = "\n\n".join(
                doc.get("text", "") for doc in documents if not doc.get("is_rules", False)
            ).strip()

            mutation_result = MutationResult(
                original_text=original_text,
                mutated_text=final_text,
                applied_changes=applied_changes,
                rejected_changes=rejected_changes,
                section_hashes_before=compute_section_hashes(original_text),
                section_hashes_after=compute_section_hashes(final_text),
            )

            engine = PostEditValidationEngine()
            validation = engine.validate(findings=findings, mutation_result=mutation_result)

            # Update validation_status in DB for each finding
            results_by_id = {r.finding_id: r for r in validation.finding_results}
            for f in findings:
                result = results_by_id.get(str(f.id))
                if result:
                    vs = result.validation_status
                    try:
                        f.validation_status = ValidationStatus(vs)
                    except ValueError:
                        f.validation_status = ValidationStatus.SKIPPED

            db.commit()

            return {
                **state,
                "post_edit_validation": validation.to_dict(),
                "error": None,
            }

        except Exception as exc:
            db.rollback()
            return {**state, "error": str(exc)}
        finally:
            db.close()
