from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.persistence.repositories.finding import FindingRepository
from app.persistence.repositories.report import ReportRepository
from app.persistence.repositories.run import RunRepository
from app.persistence.repositories.workflow_event import (
    WorkflowEventRepository,
)
from app.persistence.repositories.workflow_result import (
    WorkflowResultRepository,
)
from app.schemas.run import (
    HumanDecisionRequest,
    ReviewResponse,
    RunCreate,
    RunDetailsResponse,
    RunResponse,
    WorkflowEventResponse,
    WorkflowRunResponse,
    FindingResponse,
)
from app.services.run_service import RunService
from app.services.workflow_event_service import (
    WorkflowEventService,
)
from app.services.workflow_result_service import (
    WorkflowResultService,
)
from app.workflow.service import WorkflowService

router = APIRouter(
    prefix="/runs",
    tags=["Runs"],
)


def get_run_service(
    db: Session = Depends(get_db),  # noqa: B008
) -> RunService:
    run_repository = RunRepository(db)
    workflow_service = WorkflowService()
    finding_repository = FindingRepository(db)
    report_repository = ReportRepository(db)
    workflow_event_repository = WorkflowEventRepository(db)
    workflow_result_repository = WorkflowResultRepository(db)

    workflow_result_service = WorkflowResultService(
        workflow_result_repository,
    )

    workflow_event_service = WorkflowEventService(
        workflow_event_repository,
    )

    return RunService(
        repository=run_repository,
        workflow_service=workflow_service,
        workflow_result_service=workflow_result_service,
        workflow_event_service=workflow_event_service,
        finding_repository=finding_repository,
        report_repository=report_repository,
        workflow_event_repository=workflow_event_repository,
        workflow_result_repository=workflow_result_repository,
    )


@router.get(
    "",
    response_model=list[RunResponse],
)
def get_runs(
    db: Session = Depends(get_db),  # noqa: B008
    service: RunService = Depends(get_run_service),  # noqa: B008
) -> list[RunResponse]:
    return service.get_runs()


from fastapi import APIRouter, Depends, HTTPException, status, Request


# ... (rest of imports)

@router.post(
    "",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_run(
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
    service: RunService = Depends(get_run_service),  # noqa: B008
) -> RunResponse:
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        name = form.get("name")
        if not name or not str(name).strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run name is required")
        
        uploaded_files = form.getlist("files")
        if not uploaded_files:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one document is required")

        rules_file = form.get("rules_file")
        from fastapi import UploadFile
        rules_upload: UploadFile | None = None
        if rules_file and hasattr(rules_file, "filename") and rules_file.filename:
            rules_upload = rules_file

        from app.api.routes_ingest import get_document_service
        doc_service = get_document_service(db)

        try:
            run = service.create_run_with_documents(
                name=str(name),
                files=uploaded_files,
                rules_file=rules_upload,
                doc_service=doc_service,
            )
        except ValueError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )
    else:
        try:
            payload_json = await request.json()
            name = payload_json.get("name")
            if name is None:
                raise HTTPException(status_code=422, detail="name is required")
            if not isinstance(name, str) or len(name) < 1 or len(name) > 255:
                raise HTTPException(status_code=422, detail="Invalid name length")
        except Exception as exc:
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=422, detail="Invalid JSON payload")

        run = service.create_run(name)

    db.commit()
    db.refresh(run)

    return run


@router.get(
    "/{run_id}",
    response_model=RunResponse,
)
def get_run(
    run_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    service: RunService = Depends(get_run_service),  # noqa: B008
) -> RunResponse:

    run = service.get_run(run_id)

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    return run


@router.post(
    "/{run_id}/start",
    response_model=WorkflowRunResponse,
)
def start_workflow(
    run_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    service: RunService = Depends(get_run_service),  # noqa: B008
) -> WorkflowRunResponse:

    run = service.get_run(run_id)

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    try:
        result = service.start_workflow(run)

        db.commit()
        db.refresh(run)

        return WorkflowRunResponse(
            thread_id=result["thread_id"],
            state=result["state"],
        )

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        service.fail_run(run, str(exc))
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Workflow failed to start",
        ) from exc


@router.post(
    "/{run_id}/decision",
    response_model=WorkflowRunResponse,
)
def submit_human_decision(
    run_id: UUID,
    payload: HumanDecisionRequest,
    db: Session = Depends(get_db),  # noqa: B008
    service: RunService = Depends(get_run_service),  # noqa: B008
) -> WorkflowRunResponse:

    run = service.get_run(run_id)

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    try:
        result = service.resume_workflow(
            run,
            payload.decision,
        )

        db.commit()
        db.refresh(run)

        return WorkflowRunResponse(
            thread_id=result["thread_id"],
            state=result["state"],
        )

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        service.fail_run(run, str(exc))
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Workflow could not be resumed",
        ) from exc


@router.get(
    "/{run_id}/events",
    response_model=list[WorkflowEventResponse],
)
def get_workflow_events(
    run_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    service: RunService = Depends(get_run_service),  # noqa: B008
) -> list[WorkflowEventResponse]:

    run = service.get_run(run_id)

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    repository = WorkflowEventRepository(db)
    service = WorkflowEventService(repository)

    return service.get_events(run_id)


@router.get(
    "/{run_id}/details",
    response_model=RunDetailsResponse,
)
def get_run_details(
    run_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    service: RunService = Depends(get_run_service),  # noqa: B008
) -> RunDetailsResponse:

    result = service.get_run_details(run_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    return RunDetailsResponse(
        run=result["run"],
        findings=result["findings"],
        report=result["report"],
        workflow_events=result["workflow_events"],
        workflow_result=result["workflow_result"],
    )


@router.get(
    "/{run_id}/review",
    response_model=ReviewResponse,
)
def get_review(
    run_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    service: RunService = Depends(get_run_service),  # noqa: B008
) -> ReviewResponse:

    result = service.get_review(run_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    return ReviewResponse(**result)


@router.post(
    "/{run_id}/cancel",
    response_model=RunResponse,
)
def cancel_run(
    run_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    service: RunService = Depends(get_run_service),  # noqa: B008
) -> RunResponse:
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    try:
        service.cancel_run(run)
        db.commit()
        db.refresh(run)
        return run
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.delete(
    "/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_run(
    run_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    service: RunService = Depends(get_run_service),  # noqa: B008
) -> None:
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    try:
        service.delete_run(run)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


from pydantic import BaseModel, Field
from typing import Literal

class FindingDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]


@router.post(
    "/{run_id}/findings/{finding_id}/decision",
    response_model=FindingResponse,
)
def submit_finding_decision(
    run_id: UUID,
    finding_id: UUID,
    payload: FindingDecisionRequest,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> FindingResponse:
    from app.persistence.models.finding import Finding
    from app.core.constants import ReviewDecision, RunStatus

    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found",
        )

    if finding.run_id != run_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Finding does not belong to this run",
        )

    decision_lower = payload.decision.lower()
    if decision_lower == "approve":
        finding.review_decision = ReviewDecision.APPROVED
    elif decision_lower == "reject":
        finding.review_decision = ReviewDecision.REJECTED
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid decision value",
        )

    db.commit()
    db.refresh(finding)

    # Check if all decisions are made
    pending_count = db.query(Finding).filter(
        Finding.run_id == run_id,
        Finding.review_decision == ReviewDecision.PENDING
    ).count()

    if pending_count == 0:
        run = service.get_run(run_id)
        if run and run.status == RunStatus.WAITING_FOR_REVIEW:
            try:
                service.resume_workflow(run, "approve")
                db.commit()
            except Exception:
                db.rollback()

    return finding


@router.post(
    "/{run_id}/updates",
    response_model=RunResponse | None,
    status_code=status.HTTP_200_OK,
)
def trigger_run_update(
    run_id: UUID,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> RunResponse | None:
    """
    Trigger watched folder processing to check for new documents and execute incremental updates.
    """
    from app.core.config import settings
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    # Re-use same service layer
    update_run = service.detect_and_process_updates(
        run=run,
        watch_folder=settings.DOCTASK_WATCH_FOLDER,
        db=db
    )
    return update_run