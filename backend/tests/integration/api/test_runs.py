from uuid import uuid4
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.persistence.models.run import Run
from app.core.constants import RunStatus, WorkflowStage


client = TestClient(app)


class TestRunAPI:

    def test_create_run_successfully(self):
        # Arrange
        payload = {
            "name": "Contract Review",
        }

        # Act
        response = client.post(
            "/api/v1/runs",
            json=payload,
        )

        # Assert
        assert response.status_code == 201

        body = response.json()

        assert body["name"] == "Contract Review"
        assert body["status"] == "pending"
        assert body["stage"] == "ingestion"
        assert body["id"] is not None

    def test_create_run_with_empty_name(self):
        # Arrange
        payload = {
            "name": "",
        }

        # Act
        response = client.post(
            "/api/v1/runs",
            json=payload,
        )

        # Assert
        assert response.status_code == 422

    def test_create_run_without_name(self):
        # Arrange
        payload = {}

        # Act
        response = client.post(
            "/api/v1/runs",
            json=payload,
        )

        # Assert
        assert response.status_code == 422

    def test_create_run_with_name_at_max_length(self):
        # Arrange
        payload = {
            "name": "A" * 255,
        }

        # Act
        response = client.post(
            "/api/v1/runs",
            json=payload,
        )

        # Assert
        assert response.status_code == 201
        assert response.json()["name"] == "A" * 255

    def test_create_run_with_name_over_max_length(self):
        # Arrange
        payload = {
            "name": "A" * 256,
        }

        # Act
        response = client.post(
            "/api/v1/runs",
            json=payload,
        )

        # Assert
        assert response.status_code == 422

    def test_get_existing_run(self):
        # Arrange
        create_response = client.post(
            "/api/v1/runs",
            json={
                "name": "Existing Run",
            },
        )

        run_id = create_response.json()["id"]

        # Act
        response = client.get(
            f"/api/v1/runs/{run_id}",
        )

        # Assert
        assert response.status_code == 200

        body = response.json()

        assert body["id"] == run_id
        assert body["name"] == "Existing Run"

    def test_get_non_existing_run(self):
        # Arrange
        run_id = uuid4()

        # Act
        response = client.get(
            f"/api/v1/runs/{run_id}",
        )

        # Assert
        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"

    def test_get_run_with_invalid_uuid(self):
        # Act
        response = client.get(
            "/api/v1/runs/not-a-valid-uuid",
        )

        # Assert
        assert response.status_code == 422


@pytest.fixture
def mock_run_service():
    from app.api.routes_runs import get_run_service
    from app.services.run_service import RunService
    from app.persistence.repositories.run import RunRepository
    from app.core.database import get_db
    from fastapi import Depends
    
    mock_workflow_service = MagicMock()
    
    def override_get_run_service(db = Depends(get_db)):
        return RunService(
            repository=RunRepository(db),
            workflow_service=mock_workflow_service,
        )
        
    app.dependency_overrides[get_run_service] = override_get_run_service
    yield mock_workflow_service
    app.dependency_overrides.clear()


@pytest.fixture
def client_fixture():
    return TestClient(app)


def test_start_workflow(client_fixture, mock_run_service):
    create_response = client_fixture.post(
        "/api/v1/runs",
        json={"name": "Test Run"},
    )
    run_id = create_response.json()["id"]

    mock_run_service.start.return_value = {
        "thread_id": f"thread-{run_id}",
        "state": {
            "status": "running",
        },
    }

    response = client_fixture.post(f"/api/v1/runs/{run_id}/start")
    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"] == f"thread-{run_id}"
    assert body["state"]["status"] == "running"
    mock_run_service.start.assert_called_once()
    _, kwargs = mock_run_service.start.call_args
    assert kwargs["thread_id"] == str(run_id)


def test_start_workflow_run_not_found(client_fixture, mock_run_service):
    run_id = uuid4()
    response = client_fixture.post(f"/api/v1/runs/{run_id}/start")
    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"


def test_submit_approve_decision(client_fixture, mock_run_service, db_session):
    create_response = client_fixture.post(
        "/api/v1/runs",
        json={"name": "Test Run"},
    )
    run_id = create_response.json()["id"]

    run = db_session.query(Run).filter(Run.id == run_id).first()
    run.status = RunStatus.WAITING_FOR_REVIEW
    run.thread_id = f"thread-{run_id}"
    db_session.commit()

    mock_run_service.resume.return_value = {
        "thread_id": f"thread-{run_id}",
        "state": {
            "human_decision": "approve",
        },
    }

    response = client_fixture.post(
        f"/api/v1/runs/{run_id}/decision",
        json={"decision": "approve"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"] == f"thread-{run_id}"
    assert body["state"]["human_decision"] == "approve"
    mock_run_service.resume.assert_called_once_with(
        thread_id=f"thread-{run_id}",
        decision="approve",
    )


def test_submit_reject_decision(client_fixture, mock_run_service, db_session):
    create_response = client_fixture.post(
        "/api/v1/runs",
        json={"name": "Test Run"},
    )
    run_id = create_response.json()["id"]

    run = db_session.query(Run).filter(Run.id == run_id).first()
    run.status = RunStatus.WAITING_FOR_REVIEW
    run.thread_id = f"thread-{run_id}"
    db_session.commit()

    mock_run_service.resume.return_value = {
        "thread_id": f"thread-{run_id}",
        "state": {
            "human_decision": "reject",
        },
    }

    response = client_fixture.post(
        f"/api/v1/runs/{run_id}/decision",
        json={"decision": "reject"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"] == f"thread-{run_id}"
    assert body["state"]["human_decision"] == "reject"
    mock_run_service.resume.assert_called_once_with(
        thread_id=f"thread-{run_id}",
        decision="reject",
    )


def test_submit_invalid_decision(client_fixture, mock_run_service):
    create_response = client_fixture.post(
        "/api/v1/runs",
        json={"name": "Test Run"},
    )
    run_id = create_response.json()["id"]

    response = client_fixture.post(
        f"/api/v1/runs/{run_id}/decision",
        json={"decision": "maybe"},
    )
    assert response.status_code == 422