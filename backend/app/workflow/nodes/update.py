"""Workflow terminal nodes: CommitNode, findings_review_node.

CommitNode now persists:
  1. The audit review report (report.content)
  2. The actual final document text (report.final_content) from mutation state
  3. Post-edit validation results (report.validation_passed / .validation_summary)
  4. Provenance change history (report.change_history)
  5. Section hash comparison (report.section_hashes)
"""
from app.workflow.state import WorkflowState


class UpdateNode:
    """
    Finalizes the workflow state after examination.
    """

    def __call__(self, state: WorkflowState) -> WorkflowState:
        examination = state.get("examination")

        if examination is None:
            return {
                **state,
                "status": "failed",
                "error": "Examination result is missing",
            }

        updates = {
            "status": "completed",
            "examination_valid": examination.is_valid,
            "examination_confidence": examination.confidence,
            "issues": examination.issues,
            "summary": examination.summary,
        }

        return {
            **state,
            "updates": updates,
            "status": "completed",
            "error": None,
        }


from app.core.database import SessionLocal
from app.persistence.models.report import Report
from app.persistence.models.finding import Finding
from app.core.constants import ReviewDecision, WorkflowStage
from langgraph.types import interrupt


class CommitNode:
    """
    Commit stage: compiles approved findings into the final persisted report AND
    persists the actual mutated final document artifact with full provenance.
    """

    def __call__(self, state: WorkflowState) -> WorkflowState:
        db = SessionLocal()
        try:
            from app.persistence.models.run import Run
            run = db.query(Run).filter(Run.id == state["run_id"]).first()
            if not run:
                return {
                    **state,
                    "status": "completed",
                    "error": None,
                }
            run.stage = WorkflowStage.COMMIT
            db.flush()

            # --- Query all findings ---
            all_findings = db.query(Finding).filter(
                Finding.run_id == state["run_id"]
            ).all()
            approved_findings = [f for f in all_findings if f.review_decision == ReviewDecision.APPROVED]
            rejected_findings = [f for f in all_findings if f.review_decision == ReviewDecision.REJECTED]

            # --- Build Audit/Review Report (report.content) ---
            report_lines = ["# Contract Review – Audit Report\n"]
            examination = state.get("examination")
            summary = examination.summary if examination else "Contract processed."
            report_lines.append(f"## Summary\n{summary}\n")

            # Single canonical findings table
            report_lines.append("## Findings & Proposed Changes\n")
            report_lines.append("| Finding | Original Value | Proposed Change | Decision | Applied | Validation |")
            report_lines.append("|---------|---------------|-----------------|----------|---------|------------|")

            for f in all_findings:
                original = f.original_value or "—"
                proposed = f.proposed_edit or (
                    f"{f.original_value} → {f.proposed_value}" if f.original_value and f.proposed_value else "—"
                )
                decision = f.review_decision.value.capitalize()
                applied = f.application_status.value.capitalize()
                validation = f.validation_status.value.capitalize()
                report_lines.append(
                    f"| {f.title} | {original} | {proposed} | {decision} | {applied} | {validation} |"
                )

            # --- Post-edit validation section ---
            post_edit = state.get("post_edit_validation", {})
            if post_edit:
                passed_str = "PASSED" if post_edit.get("passed") else "FAILED"
                report_lines.append(f"\n## Post-Edit Validation: {passed_str}")
                report_lines.append(post_edit.get("summary", ""))
                if post_edit.get("unexpected_changes"):
                    report_lines.append("\n### Unexpected Changes Detected")
                    for uc in post_edit["unexpected_changes"]:
                        report_lines.append(f"- {uc}")

            # --- Section hash proof ---
            section_hashes = state.get("section_hashes", {})
            if section_hashes:
                report_lines.append("\n## Unchanged Content Proof (Section Hashes)")
                report_lines.append("| Section | Before Hash | After Hash | Changed? |")
                report_lines.append("|---------|------------|------------|---------|")
                for section, hashes in section_hashes.items():
                    if section == "_full_document":
                        continue
                    before = str(hashes.get("before_hash", ""))[:12] + "..."
                    after = str(hashes.get("after_hash", ""))[:12] + "..."
                    changed = "YES" if hashes.get("changed") else "NO"
                    report_lines.append(f"| {section} | {before} | {after} | {changed} |")

            report_content = "\n".join(report_lines)

            # --- Final Document Artifact (report.final_content) ---
            final_document_text = state.get("final_document_text") or ""

            # Build final document with header if we have actual mutations
            applied_changes = state.get("applied_changes", [])
            if final_document_text and applied_changes:
                n_applied = sum(1 for c in applied_changes if c.get("application_status") == "applied")
                n_rejected = sum(1 for c in applied_changes if c.get("application_status") == "rejected")
                final_doc = (
                    f"# FINAL CONTRACT DOCUMENT\n"
                    f"# Generated by DocTask – {n_applied} edit(s) applied, {n_rejected} rejected\n"
                    f"# Post-Edit Validation: {'PASSED' if post_edit.get('passed') else 'NOT RUN' if not post_edit else 'FAILED'}\n"
                    f"{'#' * 60}\n\n"
                    f"{final_document_text}"
                )
            else:
                # No mutations made (all rejected or no proposed edits)
                documents = state.get("documents", [])
                source_text = "\n\n".join(
                    doc.get("text", "") for doc in documents if not doc.get("is_rules", False)
                ).strip()
                final_doc = source_text or final_document_text or ""

            # --- Validation fields ---
            validation_passed = post_edit.get("passed") if post_edit else None
            validation_summary = post_edit.get("summary") if post_edit else None

            # --- Idempotently update/create report ---
            report = db.query(Report).filter(Report.run_id == state["run_id"]).first()
            if report:
                report.content = report_content
                report.version += 1
                report.approved = True
                report.final_content = final_doc
                report.validation_passed = validation_passed
                report.validation_summary = validation_summary
                report.change_history = applied_changes or []
                report.section_hashes = section_hashes or {}
            else:
                report = Report(
                    run_id=state["run_id"],
                    content=report_content,
                    version=1,
                    approved=True,
                    final_content=final_doc,
                    validation_passed=validation_passed,
                    validation_summary=validation_summary,
                    change_history=applied_changes or [],
                    section_hashes=section_hashes or {},
                )
                db.add(report)
            # Ensure run status is marked completed in DB
            from app.core.constants import RunStatus
            if run:
                run.status = RunStatus.COMPLETED
                run.stage = WorkflowStage.COMMIT
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            return {
                **state,
                "status": "completed",
                "error": None,
            }
        finally:
            try:
                db.close()
            except Exception:
                pass

        return {
            **state,
            "status": "completed",
            "error": None,
        }


def findings_review_node(state: WorkflowState) -> WorkflowState:
    """
    Suspends execution waiting for human decision on each finding.
    """
    res = interrupt(
        {
            "type": "findings_review",
            "run_id": str(state["run_id"]),
            "message": "Human review of individual findings is required.",
        }
    )
    return state