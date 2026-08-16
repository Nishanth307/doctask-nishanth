from unittest.mock import Mock, MagicMock
from uuid import uuid4
import pytest
from app.core.constants import ReviewDecision, RunStatus, WorkflowStage
from app.persistence.models.finding import Finding
from app.persistence.models.run import Run
from app.persistence.models.report import Report
from app.services.run_service import RunService
from app.workflow.service import WorkflowService
from app.workflow.graph import build_workflow
from app.core.database import SessionLocal


class TestKillAndResumeIntegration:

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.db = SessionLocal()
        # Clean up database tables for these tests
        self.db.query(Report).delete()
        self.db.query(Finding).delete()
        self.db.query(Run).delete()
        self.db.commit()
        yield
        self.db.query(Report).delete()
        self.db.query(Finding).delete()
        self.db.query(Run).delete()
        self.db.commit()
        self.db.close()

    def test_mid_workflow_resume_mocked(self):
        # Create a mock run service and check pointer flow
        run_id = uuid4()
        run = Run(
            id=run_id,
            name="Kill and Resume Run",
            status=RunStatus.RUNNING,
            stage=WorkflowStage.INGESTION,
        )
        self.db.add(run)
        self.db.commit()

        # Simulate process restart/recreation of WorkflowService
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "status": "completed",
            "run_id": run_id,
        }
        
        ws = WorkflowService(graph=mock_graph)
        result = ws.start(
            state={"run_id": run_id},
            thread_id=str(run_id)
        )
        
        assert result["thread_id"] == str(run_id)
        assert result["state"]["status"] == "completed"

    def test_human_review_and_commit_boundary(self):
        # Create run in WAITING_FOR_REVIEW
        run_id = uuid4()
        run = Run(
            id=run_id,
            name="Checkpoint Run",
            status=RunStatus.WAITING_FOR_REVIEW,
            stage=WorkflowStage.REVIEW,
            thread_id=str(run_id),
        )
        self.db.add(run)
        
        # Add a finding in PENDING state
        finding = Finding(
            id=uuid4(),
            run_id=run_id,
            title="Policy violation",
            description="Found a contract mismatch.",
            review_decision=ReviewDecision.PENDING,
        )
        self.db.add(finding)
        self.db.commit()

        # Simulate process termination by recreating database connections and services
        db2 = SessionLocal()
        run_fetched = db2.query(Run).filter(Run.id == run_id).first()
        assert run_fetched.status == RunStatus.WAITING_FOR_REVIEW
        
        # Approve finding
        finding_fetched = db2.query(Finding).filter(Finding.run_id == run_id).first()
        finding_fetched.review_decision = ReviewDecision.APPROVED
        db2.commit()

        # Simulate WorkflowService resuming
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "status": "completed",
            "run_id": run_id,
        }
        ws = WorkflowService(graph=mock_graph)
        res = ws.resume(thread_id=str(run_id), decision="approve")
        
        assert res["state"]["status"] == "completed"
        db2.close()

    def test_commit_idempotency(self):
        from app.workflow.nodes.update import CommitNode
        run_id = uuid4()
        
        # Create run in DB
        run = Run(
            id=run_id,
            name="Commit Idempotency Test",
            status=RunStatus.RUNNING,
            stage=WorkflowStage.COMMIT,
        )
        self.db.add(run)
        
        # Add approved finding
        finding = Finding(
            id=uuid4(),
            run_id=run_id,
            title="Policy violation",
            description="Found a mismatch.",
            review_decision=ReviewDecision.APPROVED,
        )
        self.db.add(finding)
        self.db.commit()

        commit_node = CommitNode()
        state = {"run_id": run_id}
        
        # First commit execution
        res1 = commit_node(state)
        assert res1["status"] == "completed"
        
        # Verify exactly 1 report exists
        reports = self.db.query(Report).filter(Report.run_id == run_id).all()
        assert len(reports) == 1
        assert reports[0].version == 1
        
        # Second commit execution (simulate resume/re-run at commit boundary)
        res2 = commit_node(state)
        assert res2["status"] == "completed"
        
        # Verify report count did not duplicate
        self.db.expire_all()
        reports = self.db.query(Report).filter(Report.run_id == run_id).all()
        assert len(reports) == 1
        assert reports[0].version == 2 # Version updated idempotently, no duplicate report records!
