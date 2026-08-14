from unittest.mock import MagicMock
from uuid import uuid4

from app.core.constants import WorkflowStage
from app.persistence.models.workflow_event import WorkflowEvent
from app.persistence.repositories.workflow_event import (
    WorkflowEventRepository,
)


class TestWorkflowEventRepository:

    def setup_method(self):
        self.db = MagicMock()
        self.repository = WorkflowEventRepository(self.db)

    def test_get_by_run_id_returns_events(self):
        # Arrange
        run_id = uuid4()

        event_1 = WorkflowEvent(
            run_id=run_id,
            stage=WorkflowStage.CLASSIFICATION,
            status="completed",
            message="Classification completed",
        )

        event_2 = WorkflowEvent(
            run_id=run_id,
            stage=WorkflowStage.EXTRACTION,
            status="completed",
            message="Extraction completed",
        )

        scalars = self.db.scalars.return_value
        scalars.all.return_value = [
            event_1,
            event_2,
        ]

        # Act
        result = self.repository.get_by_run_id(run_id)

        # Assert
        assert result == [
            event_1,
            event_2,
        ]

        self.db.scalars.assert_called_once()

    def test_get_by_run_id_returns_empty_list(self):
        # Arrange
        run_id = uuid4()

        self.db.scalars.return_value.all.return_value = []

        # Act
        result = self.repository.get_by_run_id(run_id)

        # Assert
        assert result == []
