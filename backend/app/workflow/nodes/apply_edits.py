"""Apply Edits workflow node.

After all findings have been reviewed (approved/rejected), this node:
1. Loads all findings for the run.
2. Retrieves the source document text.
3. Invokes DocumentMutationEngine to apply approved edits surgically.
4. Updates each finding's application_status in the database.
5. Returns the mutated final document text and change records in state.
"""
from __future__ import annotations

from app.workflow.state import WorkflowState


class ApplyEditsNode:
    """Apply approved finding edits to the source document."""

    def __call__(self, state: WorkflowState) -> WorkflowState:
        run_id = state.get("run_id")
        if not run_id:
            return {**state, "error": "run_id missing in state", "status": "failed"}

        from app.core.database import SessionLocal
        from app.core.constants import ApplicationStatus, ReviewDecision
        from app.persistence.models.finding import Finding
        from app.persistence.models.run import Run
        from app.services.mutation_service import DocumentMutationEngine

        db = SessionLocal()
        try:
            run = db.query(Run).filter(Run.id == run_id).first()
            if not run:
                # No persisted run (e.g. test context) – skip mutation, treat as no-op
                return {
                    **state,
                    "final_document_text": "",
                    "applied_changes": [],
                    "rejected_changes": [],
                    "section_hashes": {},
                    "error": None,
                }

            findings = db.query(Finding).filter(Finding.id.in_(
                [f["id"] for f in state.get("findings", [])]
            ) if state.get("findings") else Finding.run_id == run_id).all()

            if not findings:
                findings = db.query(Finding).filter(Finding.run_id == run_id).all()

            # Get source document text from state or from documents
            documents = state.get("documents", [])
            source_text = "\n\n".join(
                doc.get("text", "") for doc in documents if not doc.get("is_rules", False)
            ).strip()

            if not source_text:
                # No source text to mutate — cannot apply any edits.
                # Approved findings are FAILED (not applied), rejected are REJECTED.
                for f in findings:
                    if f.review_decision == ReviewDecision.APPROVED:
                        f.application_status = ApplicationStatus.FAILED
                    elif f.review_decision == ReviewDecision.REJECTED:
                        f.application_status = ApplicationStatus.REJECTED
                db.commit()
                return {
                    **state,
                    "final_document_text": "",
                    "applied_changes": [],
                    "rejected_changes": [],
                    "error": "No source document text available for mutation.",
                }

            engine = DocumentMutationEngine()
            mutation_result = engine.apply_approved_edits(
                source_text=source_text,
                findings=findings,
                run_id=str(run_id),
            )

            # Update application_status for each finding in DB using the actual status from the change record
            # Build a lookup: finding_id → application_status string from ChangeRecord
            all_change_records = (
                mutation_result.applied_changes
                + mutation_result.rejected_changes
                + mutation_result.failed_changes
            )
            status_by_finding: dict[str, str] = {
                cr.finding_id: cr.application_status for cr in all_change_records
            }

            # Map ChangeRecord status strings to ApplicationStatus enum values
            status_enum_map = {
                "applied": ApplicationStatus.APPLIED,
                "rejected": ApplicationStatus.REJECTED,
                "failed": ApplicationStatus.FAILED,
                "not_applicable": ApplicationStatus.NOT_APPLICABLE,
            }

            for f in findings:
                fid = str(f.id)
                if fid in status_by_finding:
                    status_str = status_by_finding[fid]
                    f.application_status = status_enum_map.get(status_str, ApplicationStatus.FAILED)

            db.commit()

            return {
                **state,
                "final_document_text": mutation_result.mutated_text,
                "applied_changes": mutation_result.to_change_history(),
                "rejected_changes": [cr.change_id for cr in mutation_result.rejected_changes],
                "section_hashes": mutation_result.hash_comparison,
                "error": None,
            }

        except Exception as exc:
            db.rollback()
            return {**state, "error": str(exc), "status": "failed"}
        finally:
            db.close()
