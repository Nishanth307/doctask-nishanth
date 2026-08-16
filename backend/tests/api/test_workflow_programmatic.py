import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.core.database import SessionLocal
from app.persistence.models.run import Run
from app.persistence.models.document import Document
from app.persistence.models.finding import Finding
from app.persistence.models.report import Report
from app.main import app

class TestWorkflowProgrammaticDriver:

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.db = SessionLocal()
        self.db.query(Report).delete()
        self.db.query(Finding).delete()
        self.db.query(Document).delete()
        self.db.query(Run).delete()
        self.db.commit()
        self.client = TestClient(app)
        yield
        self.db.query(Report).delete()
        self.db.query(Finding).delete()
        self.db.query(Document).delete()
        self.db.query(Run).delete()
        self.db.commit()
        self.db.close()

    def test_complete_programmatic_workflow_flow(self):
        # 1. Create run through REST API
        response = self.client.post("/api/v1/runs", json={"name": "Programmatic Test Run"})
        assert response.status_code == 201
        run_data = response.json()
        run_id = run_data["id"]
        assert run_data["name"] == "Programmatic Test Run"
        assert run_data["status"] == "pending"

        # 2. Upload source document through REST API
        files = {"file": ("contract.txt", b"Some contract text facts.", "text/plain")}
        response = self.client.post(f"/api/v1/runs/{run_id}/documents?is_rules=false", files=files)
        assert response.status_code == 201
        doc_data = response.json()
        assert doc_data["filename"] == "contract.txt"
        assert doc_data["is_rules"] is False

        # 3. Upload review rules document through REST API
        files_rules = {"file": ("playbook.txt", b"Some checklist rules text.", "text/plain")}
        response = self.client.post(f"/api/v1/runs/{run_id}/documents?is_rules=true", files=files_rules)
        assert response.status_code == 201
        rules_data = response.json()
        assert rules_data["filename"] == "playbook.txt"
        assert rules_data["is_rules"] is True

        # 4. Start workflow
        # Mock model factory / llm return outputs to bypass external key dependency
        # Since we use mocked nodes in graph test execution contexts, let's verify endpoint accepts it
        response = self.client.post(f"/api/v1/runs/{run_id}/start")
        # Start endpoint returns status code and thread_id
        assert response.status_code in [200, 201]
        start_data = response.json()
        assert "thread_id" in start_data

        # 5. Retrieve status and findings
        response = self.client.get(f"/api/v1/runs/{run_id}")
        assert response.status_code == 200
        run_data = response.json()
        assert run_data["name"] == "Programmatic Test Run"
        
        # Verify ownership / validation check:
        # Invalid finding ID on run returns 404/400
        invalid_finding_id = uuid4()
        response = self.client.post(
            f"/api/v1/runs/{run_id}/findings/{invalid_finding_id}/decision",
            json={"decision": "approve"}
        )
        assert response.status_code == 404
