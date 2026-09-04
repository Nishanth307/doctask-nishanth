from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.constants import RunStatus
from app.core.database import get_db
from app.api.routes_runs import get_run_service
from app.main import app
from app.persistence.models.run import Run
from app.services.run_service import RunService


def create_mock_run(
    run_id=None,
    name="Contract Review",
):
    from datetime import datetime, timezone
    from app.core.constants import RunStatus, WorkflowStage
    return Run(
        id=run_id or uuid4(),
        name=name,
        status=RunStatus.PENDING,
        stage=WorkflowStage.INGESTION,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestRunRoutes:

    def setup_method(self):
        self.db = Mock()
        self.service = Mock(spec=RunService)

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_run_service] = (
            lambda: self.service
        )

        self.client = TestClient(app)

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_start_workflow_run_not_found(self):
        run_id = uuid4()

        self.service.get_run.return_value = None

        response = self.client.post(
            f"/api/v1/runs/{run_id}/start",
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"

    def test_start_workflow(self):
        run_id = uuid4()

        run = create_mock_run(run_id)

        self.service.get_run.return_value = run
        self.service.start_workflow.return_value = {
            "thread_id": str(run_id),
            "state": {
                "run_id": run_id,
                "retry_count": 0,
            },
        }

        response = self.client.post(
            f"/api/v1/runs/{run_id}/start",
        )

        assert response.status_code == 200

        body = response.json()

        assert body["thread_id"] == str(run_id)
        assert body["state"]["retry_count"] == 0

    def test_retry_workflow_run_not_found(self):
        run_id = uuid4()
        self.service.get_run.return_value = None

        response = self.client.post(
            f"/api/v1/runs/{run_id}/retry",
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"

    def test_retry_workflow_success(self):
        run_id = uuid4()
        run = create_mock_run(run_id)
        run.status = RunStatus.FAILED

        self.service.get_run.return_value = run
        self.service.retry_workflow.return_value = {
            "thread_id": str(run_id),
            "state": {
                "run_id": run_id,
                "status": "running",
            },
        }

        response = self.client.post(
            f"/api/v1/runs/{run_id}/retry",
        )

        assert response.status_code == 200
        body = response.json()
        assert body["thread_id"] == str(run_id)
        assert body["state"]["status"] == "running"

    def test_submit_approve_decision(self):
        run_id = uuid4()

        run = create_mock_run(run_id)

        self.service.get_run.return_value = run
        self.service.resume_workflow.return_value = {
            "thread_id": str(run_id),
            "state": {
                "human_decision": "approve",
            },
        }

        response = self.client.post(
            f"/api/v1/runs/{run_id}/decision",
            json={
                "decision": "approve",
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert body["thread_id"] == str(run_id)
        assert body["state"]["human_decision"] == "approve"

    def test_submit_reject_decision(self):
        run_id = uuid4()

        run = create_mock_run(run_id)

        self.service.get_run.return_value = run
        self.service.resume_workflow.return_value = {
            "thread_id": str(run_id),
            "state": {
                "human_decision": "reject",
            },
        }

        response = self.client.post(
            f"/api/v1/runs/{run_id}/decision",
            json={
                "decision": "reject",
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert body["state"]["human_decision"] == "reject"

    def test_submit_invalid_decision(self):
        run_id = uuid4()

        response = self.client.post(
            f"/api/v1/runs/{run_id}/decision",
            json={
                "decision": "maybe",
            },
        )

        assert response.status_code == 422

    def test_submit_decision_run_not_found(self):
        run_id = uuid4()

        self.service.get_run.return_value = None

        response = self.client.post(
            f"/api/v1/runs/{run_id}/decision",
            json={
                "decision": "approve",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"

    def test_submit_decision_when_run_not_waiting(self):
        run_id = uuid4()
        run = create_mock_run(run_id)

        self.service.get_run.return_value = run
        self.service.resume_workflow.side_effect = ValueError(
            "Run is not waiting for human review"
        )

        response = self.client.post(
            f"/api/v1/runs/{run_id}/decision",
            json={
                "decision": "approve",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Run is not waiting for human review"
        )

    def test_get_workflow_events(self):
        from app.persistence.models.workflow_event import WorkflowEvent
        from app.core.constants import WorkflowStage

        run_id = uuid4()
        run = create_mock_run(run_id)

        self.service.get_run.return_value = run

        from datetime import datetime, timezone
        event = WorkflowEvent(
            id=uuid4(),
            run_id=run.id,
            stage=WorkflowStage.CLASSIFICATION,
            status="completed",
            message="Classification completed",
            duration_ms=1200,
            created_at=datetime.now(timezone.utc),
        )

        # Mock the db session query/scalars calls to return this event
        mock_scalars = self.db.scalars.return_value
        mock_scalars.all.return_value = [event]

        response = self.client.get(
            f"/api/v1/runs/{run.id}/events",
        )

        assert response.status_code == 200
        body = response.json()

        assert len(body) == 1
        assert body[0]["run_id"] == str(run.id)
        assert body[0]["stage"] == "classification"
        assert body[0]["status"] == "completed"
        assert body[0]["message"] == "Classification completed"
        assert body[0]["duration_ms"] == 1200

    def test_get_workflow_events_returns_empty_list(self):
        run_id = uuid4()
        run = create_mock_run(run_id)

        self.service.get_run.return_value = run

        # Mock db to return empty list
        mock_scalars = self.db.scalars.return_value
        mock_scalars.all.return_value = []

        response = self.client.get(
            f"/api/v1/runs/{run.id}/events",
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_get_workflow_events_for_missing_run(self):
        run_id = uuid4()

        self.service.get_run.return_value = None

        response = self.client.get(
            f"/api/v1/runs/{run_id}/events",
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"

    def test_get_run_details_success(self):
        from datetime import datetime, timezone
        from app.core.constants import FindingSeverity, ReviewDecision, WorkflowStage
        from app.persistence.models.finding import Finding
        from app.persistence.models.report import Report
        from app.persistence.models.workflow_event import WorkflowEvent
        from app.persistence.models.workflow_result import WorkflowResult

        run_id = uuid4()
        run = create_mock_run(run_id)

        finding = Finding(
            id=uuid4(),
            run_id=run_id,
            title="Test Finding",
            description="Test Description",
            severity=FindingSeverity.ERROR,
            review_decision=ReviewDecision.APPROVED,
            citation={},
            finding_metadata={},
            created_at=datetime.now(timezone.utc),
        )

        report = Report(
            id=uuid4(),
            run_id=run_id,
            content="Test Content",
            version=1,
            approved=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        event = WorkflowEvent(
            id=uuid4(),
            run_id=run_id,
            stage=WorkflowStage.CLASSIFICATION,
            status="completed",
            message="Completed classify",
            duration_ms=1000,
            created_at=datetime.now(timezone.utc),
        )

        result = WorkflowResult(
            id=uuid4(),
            run_id=run_id,
            status="completed",
            classification={"class": "test"},
            extracted_facts=[{"fact": "one"}],
            reconciliation={"human": False},
            examination={"valid": True},
            human_decision="approve",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.service.get_run_details.return_value = {
            "run": run,
            "findings": [finding],
            "report": report,
            "workflow_events": [event],
            "workflow_result": result,
        }

        response = self.client.get(
            f"/api/v1/runs/{run_id}/details",
        )

        assert response.status_code == 200
        body = response.json()

        assert body["run"]["id"] == str(run_id)
        assert len(body["findings"]) == 1
        assert body["findings"][0]["title"] == "Test Finding"
        assert body["report"]["content"] == "Test Content"
        assert len(body["workflow_events"]) == 1
        assert body["workflow_result"]["status"] == "completed"

    def test_get_run_details_not_found(self):
        run_id = uuid4()
        self.service.get_run_details.return_value = None

        response = self.client.get(
            f"/api/v1/runs/{run_id}/details",
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"

    def test_get_run_details_missing_optionals(self):
        run_id = uuid4()
        run = create_mock_run(run_id)

        self.service.get_run_details.return_value = {
            "run": run,
            "findings": [],
            "report": None,
            "workflow_events": [],
            "workflow_result": None,
        }

        response = self.client.get(
            f"/api/v1/runs/{run_id}/details",
        )

        assert response.status_code == 200
        body = response.json()

        assert body["run"]["id"] == str(run_id)
        assert body["findings"] == []
        assert body["report"] is None
        assert body["workflow_events"] == []
        assert body["workflow_result"] is None

    def test_get_review_success(self):
        from datetime import datetime, timezone
        from app.core.constants import FindingSeverity, ReviewDecision, RunStatus, WorkflowStage
        from app.persistence.models.finding import Finding

        run_id = uuid4()

        finding = Finding(
            id=uuid4(),
            run_id=run_id,
            title="Test Finding",
            description="Test Description",
            severity=FindingSeverity.ERROR,
            review_decision=ReviewDecision.PENDING,
            citation={},
            finding_metadata={},
            created_at=datetime.now(timezone.utc),
        )

        self.service.get_review.return_value = {
            "run_id": run_id,
            "status": RunStatus.WAITING_FOR_REVIEW,
            "stage": WorkflowStage.REVIEW,
            "requires_review": True,
            "findings": [finding],
        }

        response = self.client.get(
            f"/api/v1/runs/{run_id}/review",
        )

        assert response.status_code == 200
        body = response.json()

        assert body["run_id"] == str(run_id)
        assert body["requires_review"] is True
        assert len(body["findings"]) == 1
        assert body["findings"][0]["title"] == "Test Finding"

    def test_get_review_requires_review_false(self):
        from app.core.constants import RunStatus, WorkflowStage

        run_id = uuid4()

        self.service.get_review.return_value = {
            "run_id": run_id,
            "status": RunStatus.RUNNING,
            "stage": WorkflowStage.INGESTION,
            "requires_review": False,
            "findings": [],
        }

        response = self.client.get(
            f"/api/v1/runs/{run_id}/review",
        )

        assert response.status_code == 200
        body = response.json()

        assert body["requires_review"] is False
        assert body["findings"] == []

    def test_get_review_not_found(self):
        run_id = uuid4()
        self.service.get_review.return_value = None

        response = self.client.get(
            f"/api/v1/runs/{run_id}/review",
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"

    def test_get_runs(self):
        run = create_mock_run()
        self.service.get_runs.return_value = [run]

        response = self.client.get("/api/v1/runs")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["name"] == run.name

    def test_retry_node_success(self):
        run_id = uuid4()
        run = create_mock_run(run_id=run_id)
        run.status = RunStatus.FAILED
        self.service.get_run.return_value = run
        self.service.retry_node.return_value = {
            "thread_id": "thread-123",
            "state": {"status": "completed", "current_node": "extract"},
        }

        response = self.client.post(f"/api/v1/runs/{run_id}/retry/extract")

        assert response.status_code == 200
        body = response.json()
        assert body["thread_id"] == "thread-123"
        assert body["state"]["status"] == "completed"
        self.service.retry_node.assert_called_once_with(run, "extract")

    def test_retry_node_not_found(self):
        run_id = uuid4()
        self.service.get_run.return_value = None

        response = self.client.post(f"/api/v1/runs/{run_id}/retry/extract")

        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"

    def test_get_run_details_with_error_and_history(self):
        run_id = uuid4()
        run = create_mock_run(run_id=run_id)
        run.status = RunStatus.FAILED

        self.service.get_run_details.return_value = {
            "run": run,
            "findings": [],
            "report": None,
            "workflow_events": [],
            "workflow_result": None,
            "execution_history": [
                {
                    "node_name": "classify",
                    "status": "completed",
                    "attempt": 1,
                    "duration_ms": 150,
                    "error_type": None,
                    "error_message": None,
                    "retryable": None,
                    "timestamp": "2026-09-04T00:00:00Z",
                },
                {
                    "node_name": "extract",
                    "status": "failed",
                    "attempt": 1,
                    "duration_ms": 200,
                    "error_type": "LLM",
                    "error_message": "LLM Rate Limit",
                    "retryable": True,
                    "timestamp": "2026-09-04T00:00:01Z",
                },
            ],
            "last_error": {
                "node_name": "extract",
                "error_type": "LLM",
                "error_message": "LLM Rate Limit",
                "error_timestamp": "2026-09-04T00:00:01Z",
                "retryable": True,
                "attempt": 1,
                "checkpoint_id": "cp-1",
                "reason": None,
            },
        }

        response = self.client.get(f"/api/v1/runs/{run_id}/details")

        assert response.status_code == 200
        body = response.json()
        assert len(body["execution_history"]) == 2
        assert body["execution_history"][1]["node_name"] == "extract"
        assert body["execution_history"][1]["status"] == "failed"
        assert body["last_error"]["node_name"] == "extract"
        assert body["last_error"]["error_type"] == "LLM"
        assert body["last_error"]["retryable"] is True