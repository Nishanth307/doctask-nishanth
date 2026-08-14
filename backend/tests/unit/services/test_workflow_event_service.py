from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.constants import WorkflowStage
from app.persistence.models.workflow_event import WorkflowEvent
from app.persistence.repositories.workflow_event import (
    WorkflowEventRepository,
)
from app.services.workflow_event_service import WorkflowEventService


class TestWorkflowEventService:

    def setup_method(self):
        self.repository = Mock(
            spec=WorkflowEventRepository,
        )
        self.repository.create.side_effect = lambda event: event

        self.service = WorkflowEventService(
            self.repository,
        )

    def test_record_event(self):
        run_id = uuid4()

        result = self.service.record(
            run_id=run_id,
            stage=WorkflowStage.CLASSIFICATION,
            status="completed",
            message="Classification completed",
            duration_ms=1250,
        )

        assert isinstance(result, WorkflowEvent)
        assert result.run_id == run_id
        assert result.stage == WorkflowStage.CLASSIFICATION
        assert result.status == "completed"
        assert result.message == "Classification completed"
        assert result.duration_ms == 1250

        self.repository.create.assert_called_once_with(result)

    def test_record_event_without_optional_fields(self):
        run_id = uuid4()

        result = self.service.record(
            run_id=run_id,
            stage=WorkflowStage.EXTRACTION,
            status="started",
        )

        assert result.message is None
        assert result.duration_ms is None

    def test_get_events(self):
        run_id = uuid4()

        events = [
            WorkflowEvent(
                run_id=run_id,
                stage=WorkflowStage.CLASSIFICATION,
                status="completed",
            ),
        ]

        self.repository.get_by_run_id.return_value = events

        result = self.service.get_events(run_id)

        assert result == events

        self.repository.get_by_run_id.assert_called_once_with(
            run_id,
        )

    def test_get_events_when_empty(self):
        run_id = uuid4()

        self.repository.get_by_run_id.return_value = []

        result = self.service.get_events(run_id)

        assert result == []

    def test_record_propagates_repository_error(self):
        run_id = uuid4()

        self.repository.create.side_effect = RuntimeError(
            "Database error",
        )

        with pytest.raises(
            RuntimeError,
            match="Database error",
        ):
            self.service.record(
                run_id=run_id,
                stage=WorkflowStage.CLASSIFICATION,
                status="completed",
            )
