from uuid import UUID
from mcp.server.fastmcp import FastMCP
from app.core.database import SessionLocal
from app.services.run_service import RunService
from app.persistence.repositories.run import RunRepository
from app.persistence.repositories.finding import FindingRepository
from app.persistence.repositories.report import ReportRepository
from app.persistence.repositories.workflow_event import WorkflowEventRepository
from app.persistence.repositories.workflow_result import WorkflowResultRepository
from app.services.document_service import DocumentService
from app.persistence.repositories.document import DocumentRepository
from app.storage.storage import StorageService
from app.core.config import settings

mcp = FastMCP("DocTask")

def get_services():
    db = SessionLocal()
    run_repo = RunRepository(db)
    finding_repo = FindingRepository(db)
    report_repo = ReportRepository(db)
    event_repo = WorkflowEventRepository(db)
    result_repo = WorkflowResultRepository(db)
    
    from app.services.workflow_event_service import WorkflowEventService
    from app.services.workflow_result_service import WorkflowResultService
    from app.workflow.service import WorkflowService
    from app.api.routes_ingest import get_document_service
    
    event_service = WorkflowEventService(event_repo)
    result_service = WorkflowResultService(result_repo)
    workflow_service = WorkflowService(result_service=result_service)
    doc_service = get_document_service(db)
    
    run_service = RunService(
        run_repository=run_repo,
        document_service=doc_service,
        workflow_service=workflow_service,
        workflow_event_service=event_service,
        workflow_result_service=result_service,
        report_repository=report_repo,
        finding_repository=finding_repo,
    )
    return db, run_service, doc_service

@mcp.tool()
def create_run(name: str) -> dict:
    """Create a new document task run."""
    db, run_service, _ = get_services()
    try:
        run = run_service.create_run(name)
        db.commit()
        return {"id": str(run.id), "name": run.name, "status": run.status.value, "stage": run.stage.value}
    finally:
        db.close()

@mcp.tool()
def upload_document(run_id: str, filename: str, content_base64: str) -> dict:
    """Upload a source document (base64 encoded content)."""
    import base64
    db, run_service, doc_service = get_services()
    try:
        run = run_service.get_run(UUID(run_id))
        if not run:
            return {"error": "Run not found"}
        content = base64.b64decode(content_base64)
        doc = doc_service.upload_document(run_id=UUID(run_id), filename=filename, content=content, is_rules=False)
        db.commit()
        return {"id": str(doc.id), "filename": doc.filename, "is_rules": doc.is_rules}
    finally:
        db.close()

@mcp.tool()
def upload_review_rules(run_id: str, filename: str, content_base64: str) -> dict:
    """Upload a review rules document (base64 encoded content)."""
    import base64
    db, run_service, doc_service = get_services()
    try:
        run = run_service.get_run(UUID(run_id))
        if not run:
            return {"error": "Run not found"}
        content = base64.b64decode(content_base64)
        doc = doc_service.upload_document(run_id=UUID(run_id), filename=filename, content=content, is_rules=True)
        db.commit()
        return {"id": str(doc.id), "filename": doc.filename, "is_rules": doc.is_rules}
    finally:
        db.close()

@mcp.tool()
def start_run(run_id: str) -> dict:
    """Start workflow execution for a run."""
    db, run_service, _ = get_services()
    try:
        run = run_service.get_run(UUID(run_id))
        if not run:
            return {"error": "Run not found"}
        res = run_service.start_workflow(run)
        db.commit()
        return {"thread_id": res["thread_id"], "status": run.status.value, "stage": run.stage.value}
    finally:
        db.close()

@mcp.tool()
def get_run_status(run_id: str) -> dict:
    """Get the status of a run including pending/approved/rejected counts."""
    db, run_service, _ = get_services()
    try:
        run = run_service.get_run(UUID(run_id))
        if not run:
            return {"error": "Run not found"}
        from app.persistence.models.finding import Finding
        from app.core.constants import ReviewDecision
        findings = db.query(Finding).filter(Finding.run_id == UUID(run_id)).all()
        pending = sum(1 for f in findings if f.review_decision == ReviewDecision.PENDING)
        approved = sum(1 for f in findings if f.review_decision == ReviewDecision.APPROVED)
        rejected = sum(1 for f in findings if f.review_decision == ReviewDecision.REJECTED)
        return {
            "id": str(run.id),
            "status": run.status.value,
            "stage": run.stage.value,
            "pending_count": pending,
            "approved_count": approved,
            "rejected_count": rejected,
            "completed": run.status.value == "completed",
            "failed": run.status.value == "failed"
        }
    finally:
        db.close()

@mcp.tool()
def get_review_findings(run_id: str) -> list[dict]:
    """Get all findings/violations for a run."""
    db, run_service, _ = get_services()
    try:
        from app.persistence.models.finding import Finding
        findings = db.query(Finding).filter(Finding.run_id == UUID(run_id)).all()
        return [{
            "id": str(f.id),
            "title": f.title,
            "description": f.description,
            "severity": f.severity.value,
            "review_decision": f.review_decision.value
        } for f in findings]
    finally:
        db.close()

@mcp.tool()
def decide_finding(run_id: str, finding_id: str, decision: str) -> dict:
    """Approve or reject a specific finding for a run."""
    db, run_service, _ = get_services()
    try:
        from app.persistence.models.finding import Finding
        from app.core.constants import ReviewDecision, RunStatus
        finding = db.query(Finding).filter(Finding.id == UUID(finding_id)).first()
        if not finding:
            return {"error": "Finding not found"}
        if finding.run_id != UUID(run_id):
            return {"error": "Finding does not belong to this run"}
        
        decision_lower = decision.lower()
        if decision_lower == "approve":
            finding.review_decision = ReviewDecision.APPROVED
        elif decision_lower == "reject":
            finding.review_decision = ReviewDecision.REJECTED
        else:
            return {"error": "Invalid decision value"}
        
        db.commit()
        db.refresh(finding)
        
        pending_count = db.query(Finding).filter(
            Finding.run_id == UUID(run_id),
            Finding.review_decision == ReviewDecision.PENDING
        ).count()
        
        resumed = False
        if pending_count == 0:
            run = run_service.get_run(UUID(run_id))
            if run and run.status == RunStatus.WAITING_FOR_REVIEW:
                run_service.resume_workflow(run, "approve")
                db.commit()
                resumed = True
                
        return {"id": str(finding.id), "review_decision": finding.review_decision.value, "resumed": resumed}
    finally:
        db.close()

@mcp.tool()
def get_run_details(run_id: str) -> dict:
    """Get complete run details including report and events."""
    db, run_service, _ = get_services()
    try:
        run = run_service.get_run(UUID(run_id))
        if not run:
            return {"error": "Run not found"}
        from app.persistence.models.report import Report
        report = db.query(Report).filter(Report.run_id == UUID(run_id)).first()
        return {
            "run": {"id": str(run.id), "name": run.name, "status": run.status.value, "stage": run.stage.value},
            "report_content": report.content if report else None
        }
    finally:
        db.close()

@mcp.tool()
def process_update(run_id: str) -> dict:
    """Scan watch folder and process new documents incrementally for a run."""
    db, run_service, _ = get_services()
    try:
        from app.core.config import settings
        run = run_service.get_run(UUID(run_id))
        if not run:
            return {"error": "Run not found"}
        update_run = run_service.detect_and_process_updates(
            run=run,
            watch_folder=settings.DOCTASK_WATCH_FOLDER,
            db=db
        )
        if not update_run:
            return {"message": "No new updates detected"}
        return {
            "id": str(update_run.id),
            "name": update_run.name,
            "status": update_run.status.value,
            "stage": update_run.stage.value,
            "parent_id": str(update_run.parent_id)
        }
    finally:
        db.close()


@mcp.tool()
def get_proposed_changes(run_id: str) -> list[dict]:
    """Get all findings with original_value, proposed_value, and proposed_edit for a run.
    
    Returns the canonical proposed-change representation for each finding so a machine
    can decide which changes to approve or reject.
    """
    db, run_service, _ = get_services()
    try:
        from app.persistence.models.finding import Finding
        findings = db.query(Finding).filter(Finding.run_id == UUID(run_id)).all()
        return [{
            "id": str(f.id),
            "title": f.title,
            "description": f.description,
            "severity": f.severity.value,
            "review_decision": f.review_decision.value,
            "original_value": f.original_value,
            "proposed_value": f.proposed_value,
            "proposed_edit": f.proposed_edit or (
                f"{f.original_value} → {f.proposed_value}"
                if f.original_value and f.proposed_value else None
            ),
            "source_location": f.source_location,
            "application_status": f.application_status.value,
            "validation_status": f.validation_status.value,
        } for f in findings]
    finally:
        db.close()


@mcp.tool()
def apply_and_finalize(run_id: str) -> dict:
    """Apply all approved changes, run post-edit validation, and generate the final document.
    
    This triggers the apply_edits → validate_edits → commit nodes directly (bypassing
    the interrupt gate when all findings are already decided). Use after all findings
    have been approved or rejected via decide_finding().
    
    Returns the final document content and validation result.
    """
    db, run_service, _ = get_services()
    try:
        from app.persistence.models.finding import Finding
        from app.persistence.models.report import Report
        from app.persistence.models.run import Run
        from app.core.constants import ReviewDecision
        from app.services.mutation_service import DocumentMutationEngine
        from app.services.validation_service import PostEditValidationEngine

        run = run_service.get_run(UUID(run_id))
        if not run:
            return {"error": "Run not found"}

        findings = db.query(Finding).filter(Finding.run_id == UUID(run_id)).all()
        pending = [f for f in findings if f.review_decision == ReviewDecision.PENDING]
        if pending:
            return {
                "error": f"{len(pending)} findings still pending review. Decide all findings first.",
                "pending_finding_ids": [str(f.id) for f in pending],
            }

        # Get source text from the run's result/state if available
        from app.persistence.repositories.workflow_result import WorkflowResultRepository
        result_repo = WorkflowResultRepository(db)
        result = result_repo.get_by_run_id(UUID(run_id))
        
        source_text = ""
        if result and result.extracted_facts:
            # Try to reconstruct from any stored document text
            pass
        
        # Fall back to checking the report for existing content
        report = db.query(Report).filter(Report.run_id == UUID(run_id)).first()
        if report and report.content and not source_text:
            # We need the original document text - use documents on the run
            for doc in run.documents:
                if not doc.is_rules and doc.extracted_text:
                    source_text += doc.extracted_text + "\n\n"
            source_text = source_text.strip()

        # Apply approved edits
        engine = DocumentMutationEngine()
        mutation_result = engine.apply_approved_edits(
            source_text=source_text,
            findings=findings,
            run_id=run_id,
        )

        # Update application_status in DB
        from app.core.constants import ApplicationStatus
        applied_ids = {cr.finding_id for cr in mutation_result.applied_changes}
        rejected_ids = {cr.finding_id for cr in mutation_result.rejected_changes}
        failed_ids = {cr.finding_id for cr in mutation_result.failed_changes}
        for f in findings:
            fid = str(f.id)
            if fid in applied_ids:
                f.application_status = ApplicationStatus.APPLIED
            elif fid in rejected_ids:
                f.application_status = ApplicationStatus.REJECTED
            elif fid in failed_ids:
                f.application_status = ApplicationStatus.FAILED

        # Post-edit validation
        val_engine = PostEditValidationEngine()
        validation = val_engine.validate(findings=findings, mutation_result=mutation_result)

        # Update validation_status in DB
        from app.core.constants import ValidationStatus
        for vr in validation.finding_results:
            for f in findings:
                if str(f.id) == vr.finding_id:
                    try:
                        f.validation_status = ValidationStatus(vr.validation_status)
                    except ValueError:
                        pass

        # Persist final document to report
        change_history = mutation_result.to_change_history()
        section_hashes = mutation_result.hash_comparison
        n_applied = len(mutation_result.applied_changes)
        n_rejected = len(mutation_result.rejected_changes)

        final_doc = (
            f"# FINAL CONTRACT DOCUMENT\n"
            f"# {n_applied} edit(s) applied, {n_rejected} rejected\n"
            f"# Post-Edit Validation: {'PASSED' if validation.passed else 'FAILED'}\n"
            f"{'#' * 60}\n\n"
            f"{mutation_result.mutated_text}"
        ) if mutation_result.mutated_text else ""

        if report:
            report.final_content = final_doc
            report.validation_passed = validation.passed
            report.validation_summary = validation.summary
            report.change_history = change_history
            report.section_hashes = section_hashes
        else:
            report = Report(
                run_id=UUID(run_id),
                content="",
                version=1,
                approved=True,
                final_content=final_doc,
                validation_passed=validation.passed,
                validation_summary=validation.summary,
                change_history=change_history,
                section_hashes=section_hashes,
            )
            db.add(report)

        db.commit()

        return {
            "applied_changes": n_applied,
            "rejected_changes": n_rejected,
            "failed_changes": len(mutation_result.failed_changes),
            "validation_passed": validation.passed,
            "validation_summary": validation.summary,
            "has_final_document": bool(final_doc),
            "final_content_preview": final_doc[:500] + "..." if len(final_doc) > 500 else final_doc,
        }
    except Exception as exc:
        db.rollback()
        return {"error": str(exc)}
    finally:
        db.close()


@mcp.tool()
def export_final_document(run_id: str) -> dict:
    """Export the complete final document artifact with full provenance.
    
    Returns:
        - final_content: The actual edited contract text
        - change_history: Complete audit trail (who approved what, when, why)
        - section_hashes: SHA-256 proof that unchanged sections remained identical
        - validation_result: Post-edit validation outcome per finding
    """
    db, run_service, _ = get_services()
    try:
        from app.persistence.models.finding import Finding
        from app.persistence.models.report import Report
        from app.core.constants import ApplicationStatus, ReviewDecision

        run = run_service.get_run(UUID(run_id))
        if not run:
            return {"error": "Run not found"}

        report = db.query(Report).filter(Report.run_id == UUID(run_id)).first()
        if not report or not report.final_content:
            return {
                "error": "Final document not yet generated. Call apply_and_finalize() first.",
                "run_status": run.status.value,
            }

        findings = db.query(Finding).filter(Finding.run_id == UUID(run_id)).all()
        n_approved = sum(1 for f in findings if f.review_decision == ReviewDecision.APPROVED)
        n_rejected = sum(1 for f in findings if f.review_decision == ReviewDecision.REJECTED)
        n_applied = sum(1 for f in findings if f.application_status == ApplicationStatus.APPLIED)

        return {
            "run_id": run_id,
            "run_name": run.name,
            "status": run.status.value,
            "total_findings": len(findings),
            "approved_findings": n_approved,
            "rejected_findings": n_rejected,
            "applied_changes": n_applied,
            "validation_passed": report.validation_passed,
            "validation_summary": report.validation_summary,
            "final_content": report.final_content,
            "change_history": report.change_history or [],
            "section_hashes": report.section_hashes or {},
        }
    finally:
        db.close()
