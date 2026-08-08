from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.constants import RunStatus, WorkflowStage


class RunCreate(BaseModel):
    name: str


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: RunStatus
    stage: WorkflowStage
    create_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    error_message: str | None


# Why separate schemas from models?
# Your SQLAlchemy model is a database object.
# Your Pydantic schema is an API object.
# Don't expose your database models directly through FastAPI.
