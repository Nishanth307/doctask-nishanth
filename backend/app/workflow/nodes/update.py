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
    Commit stage that compiles approved findings into the final persisted report.
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

            # Query all APPROVED findings
            approved_findings = db.query(Finding).filter(
                Finding.run_id == state["run_id"],
                Finding.review_decision == ReviewDecision.APPROVED
            ).all()

            # Generate final report content
            report_lines = ["# Final Contract Review Report\n"]
            examination = state.get("examination")
            summary = examination.summary if examination else "Contract processed."
            report_lines.append(f"## Summary\n{summary}\n")

            if approved_findings:
                report_lines.append("## Approved Findings & Policy Violations\n")
                for finding in approved_findings:
                    report_lines.append(f"### ⚠️ {finding.title} (Severity: {finding.severity.value.upper()})")
                    report_lines.append(f"{finding.description}")
                    if finding.citation:
                        report_lines.append(f"*Citation: {finding.citation}*\n")
            else:
                report_lines.append("## Status\nNo violations or issues were found or approved.\n")

            report_content = "\n".join(report_lines)

            # Idempotently update/create report
            report = db.query(Report).filter(Report.run_id == state["run_id"]).first()
            if report:
                report.content = report_content
                report.version += 1
                report.approved = True
            else:
                report = Report(
                    run_id=state["run_id"],
                    content=report_content,
                    version=1,
                    approved=True,
                )
                db.add(report)

            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

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