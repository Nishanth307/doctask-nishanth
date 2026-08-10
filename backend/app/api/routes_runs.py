from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.persistence.repositories.run import RunRepository
from app.schemas.run import RunCreate, RunResponse
from app.services.run_service import RunService

router = APIRouter(
    prefix="/runs",
    tags=["Runs"],
)


def get_run_service(
    db: Session = Depends(get_db),  # noqa: B008
) -> RunService:
    repository = RunRepository(db)

    return RunService(repository)


@router.post(
    "",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_run(
    payload: RunCreate, db: Session = Depends(get_db)  # noqa: B008
) -> RunResponse:

    service = get_run_service(db)

    run = service.create_run(payload.name)

    db.commit()
    db.refresh(run)

    return run


@router.get(
    "/{run_id}",
    response_model=RunResponse,
)
def get_run(run_id: UUID, db: Session = Depends(get_db)) -> RunResponse:  # noqa: B008

    service = get_run_service(db)

    run = service.get_run(run_id)

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    return run
