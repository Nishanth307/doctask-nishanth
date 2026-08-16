from unittest.mock import Mock, MagicMock
from uuid import uuid4
from fastapi.testclient import TestClient
from app.core.database import get_db
from app.api.routes_runs import get_run_service
from app.main import app
from app.persistence.models.finding import Finding
from app.persistence.models.run import Run
from app.core.constants import ReviewDecision, RunStatus, FindingSeverity
from app.services.run_service import RunService


class TestFindingDecisionRoutes:

    def setup_method(self):
        self.db = MagicMock()
        self.service = MagicMock(spec=RunService)

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_run_service] = (
            lambda: self.service
        )

        self.client = TestClient(app)

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_finding_not_found(self):
        run_id = uuid4()
        finding_id = uuid4()
        self.db.query().filter().first.return_value = None

        response = self.client.post(
            f"/api/v1/runs/{run_id}/findings/{finding_id}/decision",
            json={"decision": "approve"}
        )
        assert response.status_code == 404
        assert "Finding not found" in response.json()["detail"]

    def test_finding_belongs_to_another_run(self):
        run_id = uuid4()
        another_run_id = uuid4()
        finding_id = uuid4()
        
        from datetime import datetime, timezone
        mock_finding = Finding(
            id=finding_id,
            run_id=another_run_id,
            title="Title",
            description="Desc",
            severity=FindingSeverity.WARNING,
            review_decision=ReviewDecision.PENDING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        self.db.query().filter().first.return_value = mock_finding

        response = self.client.post(
            f"/api/v1/runs/{run_id}/findings/{finding_id}/decision",
            json={"decision": "approve"}
        )
        assert response.status_code == 400
        assert "Finding does not belong to this run" in response.json()["detail"]

    def test_approve_finding_success(self):
        run_id = uuid4()
        finding_id = uuid4()
        
        from datetime import datetime, timezone
        mock_finding = Finding(
            id=finding_id,
            run_id=run_id,
            title="Title",
            description="Desc",
            severity=FindingSeverity.WARNING,
            review_decision=ReviewDecision.PENDING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        self.db.query().filter().first.return_value = mock_finding
        self.db.query().filter().count.return_value = 0 # No pending findings left
        
        mock_run = Run(id=run_id, status=RunStatus.WAITING_FOR_REVIEW)
        self.service.get_run.return_value = mock_run

        response = self.client.post(
            f"/api/v1/runs/{run_id}/findings/{finding_id}/decision",
            json={"decision": "approve"}
        )
        assert response.status_code == 200
        assert response.json()["review_decision"] == "approved"
        # Since pending count is 0, resume workflow was called
        self.service.resume_workflow.assert_called_once_with(mock_run, "approve")
