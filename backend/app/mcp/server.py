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
