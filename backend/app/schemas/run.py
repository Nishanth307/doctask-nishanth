from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import RunStatus, WorkflowStage
from typing import Literal

class RunCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: RunStatus
    stage: WorkflowStage
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    error_message: str | None


class HumanDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]

class WorkflowRunResponse(BaseModel):
    thread_id: str
    state: dict
# Why separate schemas from models?
# Your SQLAlchemy model is a database object.
# Your Pydantic schema is an API object.
# Don't expose your database models directly through FastAPI.
