from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.api.routes_runs import get_run_service
from app.main import app
from app.persistence.models.run import Run
from app.services.run_service import RunService


def create_mock_run(
    run_id=None,
    name="Contract Review",
):
    return Run(
        id=run_id or uuid4(),
        name=name,
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