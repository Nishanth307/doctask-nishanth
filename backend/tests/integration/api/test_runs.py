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


def test_get_run_details_includes_scoped_findings(client_fixture, db_session):
    from datetime import datetime, timezone
    from app.persistence.models.finding import Finding
    from app.core.constants import FindingSeverity, ReviewDecision

    # Create run 1
    create_res1 = client_fixture.post("/api/v1/runs", json={"name": "Run 1"})
    run1_id = create_res1.json()["id"]

    # Create run 2
    create_res2 = client_fixture.post("/api/v1/runs", json={"name": "Run 2"})
    run2_id = create_res2.json()["id"]

    # Add 2 findings to run 1
    f1 = Finding(
        id=uuid4(),
        run_id=run1_id,
        title="Conflicting Payment Due Period",
        description="Conflicting values were found for 'Payment Due Period'.",
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.PENDING,
        citation={
            "type": "contradiction",
            "semantic_key": "payment.due_period",
            "sources": [
                {"document": "doc1.docx", "value": "30 days", "confidence": 1.0},
                {"document": "doc2.docx", "value": "45 days", "confidence": 1.0},
            ],
        },
        finding_metadata={
            "type": "contradiction",
            "semantic_key": "payment.due_period",
            "field": "Payment Due Period",
        },
        created_at=datetime.now(timezone.utc),
    )
    f2 = Finding(
        id=uuid4(),
        run_id=run1_id,
        title="Conflicting Governing Law",
        description="Conflicting values were found for 'Governing Law'.",
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.PENDING,
        citation={"type": "contradiction"},
        finding_metadata={"type": "contradiction"},
        created_at=datetime.now(timezone.utc),
    )
    # Add 1 finding to run 2
    f3 = Finding(
        id=uuid4(),
        run_id=run2_id,
        title="Run 2 Finding",
        description="Run 2 description",
        severity=FindingSeverity.WARNING,
        review_decision=ReviewDecision.PENDING,
        citation=None,
        finding_metadata=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([f1, f2, f3])
    db_session.commit()

    # Query details for run 1
    res1 = client_fixture.get(f"/api/v1/runs/{run1_id}/details")
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1["findings"]) == 2
    f1_res = next(f for f in data1["findings"] if f["id"] == str(f1.id))
    assert f1_res["title"] == "Conflicting Payment Due Period"
    assert f1_res["severity"] == "error"
    assert f1_res["review_decision"] == "pending"
    assert f1_res["citation"]["type"] == "contradiction"
    assert len(f1_res["citation"]["sources"]) == 2
    assert f1_res["finding_metadata"]["semantic_key"] == "payment.due_period"

    # Query details for run 2 (verifies scoping)
    res2 = client_fixture.get(f"/api/v1/runs/{run2_id}/details")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["findings"]) == 1
    assert data2["findings"][0]["id"] == str(f3.id)


def test_run_details_three_pending_findings_counts(client_fixture, db_session):
    from datetime import datetime, timezone
    from app.persistence.models.finding import Finding
    from app.core.constants import FindingSeverity, ReviewDecision

    # 1. Create run with 3 pending findings
    create_res = client_fixture.post("/api/v1/runs", json={"name": "ACME 3 Findings Run"})
    run_id = create_res.json()["id"]

    f1 = Finding(
        id=uuid4(),
        run_id=run_id,
        title="Conflicting Payment Due Period",
        description="Payment due 30 days vs 45 days",
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.PENDING,
        citation={"type": "contradiction"},
        finding_metadata={"type": "contradiction"},
        created_at=datetime.now(timezone.utc),
    )
    f2 = Finding(
        id=uuid4(),
        run_id=run_id,
        title="Conflicting Termination Notice Period",
        description="Termination notice 60 days vs 30 days",
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.PENDING,
        citation={"type": "contradiction"},
        finding_metadata={"type": "contradiction"},
        created_at=datetime.now(timezone.utc),
    )
    f3 = Finding(
        id=uuid4(),
        run_id=run_id,
        title="Conflicting Governing Law",
        description="New York vs California",
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.PENDING,
        citation={"type": "contradiction"},
        finding_metadata={"type": "contradiction"},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([f1, f2, f3])
    db_session.commit()

    # 2. GET run details
    res = client_fixture.get(f"/api/v1/runs/{run_id}/details")
    assert res.status_code == 200
    data = res.json()

    # 3. Assert response
    assert len(data["findings"]) == 3
    assert data["run"]["pending_finding_count"] == 3
    assert data["run"]["approved_finding_count"] == 0
    assert data["run"]["rejected_finding_count"] == 0


def test_run_details_mixed_decision_findings(client_fixture, db_session):
    from datetime import datetime, timezone
    from app.persistence.models.finding import Finding
    from app.core.constants import FindingSeverity, ReviewDecision

    # 1. Create a run
    create_res = client_fixture.post("/api/v1/runs", json={"name": "Mixed Decisions Run"})
    run_id = create_res.json()["id"]

    # 2. Persist 3 findings: one pending, one approved, one rejected
    f_pending = Finding(
        id=uuid4(),
        run_id=run_id,
        title="Pending Finding",
        description="A pending contradiction",
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.PENDING,
        citation={"type": "contradiction"},
        finding_metadata={"type": "contradiction"},
        created_at=datetime.now(timezone.utc),
    )
    f_approved = Finding(
        id=uuid4(),
        run_id=run_id,
        title="Approved Finding",
        description="An approved contradiction",
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.APPROVED,
        citation={"type": "contradiction"},
        finding_metadata={"type": "contradiction"},
        created_at=datetime.now(timezone.utc),
    )
    f_rejected = Finding(
        id=uuid4(),
        run_id=run_id,
        title="Rejected Finding",
        description="A rejected contradiction",
        severity=FindingSeverity.WARNING,
        review_decision=ReviewDecision.REJECTED,
        citation={"type": "contradiction"},
        finding_metadata={"type": "contradiction"},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([f_pending, f_approved, f_rejected])
    db_session.commit()

    # 4. Call GET /runs/{run_id}/details
    res = client_fixture.get(f"/api/v1/runs/{run_id}/details")
    # 5. Assert status_code == 200
    assert res.status_code == 200
    data = res.json()

    # 6. Assert len(findings) == 3
    assert len(data["findings"]) == 3

    # 7. Assert all finding IDs are present
    response_ids = {f["id"] for f in data["findings"]}
    assert str(f_pending.id) in response_ids
    assert str(f_approved.id) in response_ids
    assert str(f_rejected.id) in response_ids

    # 8. Assert approved/rejected findings are still returned
    decisions = {f["id"]: f["review_decision"] for f in data["findings"]}
    assert decisions[str(f_pending.id)] == "pending"
    assert decisions[str(f_approved.id)] == "approved"
    assert decisions[str(f_rejected.id)] == "rejected"

    assert data["run"]["pending_finding_count"] == 1
    assert data["run"]["approved_finding_count"] == 1
    assert data["run"]["rejected_finding_count"] == 1


def test_run_details_completed_run_returns_findings(client_fixture, db_session):
    from datetime import datetime, timezone
    from app.persistence.models.finding import Finding
    from app.persistence.models.run import Run
    from app.core.constants import FindingSeverity, ReviewDecision, RunStatus, WorkflowStage

    # 1. Create a run and mark it completed
    create_res = client_fixture.post("/api/v1/runs", json={"name": "Completed Run"})
    run_id = create_res.json()["id"]

    run = db_session.query(Run).filter(Run.id == run_id).first()
    run.status = RunStatus.COMPLETED
    run.stage = WorkflowStage.COMMIT
    run.completed_at = datetime.now(timezone.utc)

    # 2. Add findings to the completed run
    f1 = Finding(
        id=uuid4(),
        run_id=run_id,
        title="Completed Run Finding 1",
        description="Finding description",
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.APPROVED,
        citation={"type": "contradiction"},
        finding_metadata={"type": "contradiction"},
        created_at=datetime.now(timezone.utc),
    )
    f2 = Finding(
        id=uuid4(),
        run_id=run_id,
        title="Completed Run Finding 2",
        description="Finding description 2",
        severity=FindingSeverity.WARNING,
        review_decision=ReviewDecision.REJECTED,
        citation={"type": "contradiction"},
        finding_metadata={"type": "contradiction"},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([f1, f2])
    db_session.commit()

    # 3. Call GET /runs/{run_id}/details
    res = client_fixture.get(f"/api/v1/runs/{run_id}/details")
    assert res.status_code == 200
    data = res.json()

    # 4. Assert findings are still returned when run is completed
    assert len(data["findings"]) == 2
    assert data["run"]["status"] == "completed"
    assert data["run"]["stage"] == "commit"
    finding_ids = [f["id"] for f in data["findings"]]
    assert str(f1.id) in finding_ids
    assert str(f2.id) in finding_ids