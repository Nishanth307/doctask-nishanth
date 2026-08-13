from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.persistence.repositories.run import RunRepository
from app.persistence.repositories.workflow_result import (
    WorkflowResultRepository,
)
from app.schemas.run import (
    HumanDecisionRequest,
    RunCreate,
    RunResponse,
    WorkflowRunResponse,
)
from app.services.run_service import RunService
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

    workflow_result_repository = WorkflowResultRepository(db)
    workflow_result_service = WorkflowResultService(
        workflow_result_repository,
    )

    return RunService(
        repository=run_repository,
        workflow_service=workflow_service,
        workflow_result_service=workflow_result_service,
    )


@router.post(
    "",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_run(
    payload: RunCreate,
    db: Session = Depends(get_db),  # noqa: B008
    service: RunService = Depends(get_run_service),  # noqa: B008
) -> RunResponse:

    run = service.create_run(payload.name)

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