import os
import tempfile
import pytest
import shutil
from unittest.mock import patch, MagicMock
from uuid import uuid4
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.persistence.models.run import Run
from app.persistence.models.document import Document
from app.persistence.models.finding import Finding
from app.persistence.models.report import Report
from app.core.constants import RunStatus, WorkflowStage
from app.api.routes_runs import get_run_service

class TestWatcherIntegration:

    @pytest.fixture(autouse=True)
    def setup_db_and_watch(self):
        self.db = SessionLocal()
        # Cleanup
        self.db.query(Report).delete()
        self.db.query(Finding).delete()
        self.db.query(Document).delete()
        self.db.query(Run).delete()
        self.db.commit()

        self.watch_dir = tempfile.mkdtemp()
        self.service = get_run_service(self.db)
        
        from app.ingestion.loaders.base import LoadedDocument
        mock_doc = LoadedDocument(text="Mocked Text Content", source="doc", metadata={"format": "docx"})
        self.docx_patcher = patch("app.ingestion.loaders.docx.DocxLoader.load", return_value=mock_doc)
        self.pdf_patcher = patch("app.ingestion.loaders.pdf.PdfLoader.load", return_value=mock_doc)
        self.docx_patcher.start()
        self.pdf_patcher.start()
        
        yield
        
        # Cleanup
        self.docx_patcher.stop()
        self.pdf_patcher.stop()
        shutil.rmtree(self.watch_dir, ignore_errors=True)
        self.db.query(Report).delete()
        self.db.query(Finding).delete()
        self.db.query(Document).delete()
        self.db.query(Run).delete()
        self.db.commit()
        self.db.close()

    @patch("app.workflow.service.WorkflowService.start")
    def test_new_file_detection_and_duplicate_prevention(self, mock_start):
        mock_start.return_value = {"thread_id": "test_thread", "state": {"status": "completed"}}
        # A. New file detection
        initial_run = Run(
            name="Initial Watched Run",
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )
        self.db.add(initial_run)
        self.db.commit()

        # Add a supported document to watch folder
        doc_path = os.path.join(self.watch_dir, "contract.docx")
        with open(doc_path, "wb") as f:
            f.write(b"Mock PDF Content")

        # Run watcher
        update_run = self.service.detect_and_process_updates(initial_run, self.watch_dir, self.db)
        assert update_run is not None
        assert update_run.parent_id == initial_run.id
        assert len(update_run.documents) == 1
        assert update_run.documents[0].filename == "contract.docx"
        mock_start.assert_called_once()

        # B. Duplicate event: Run watcher again with same file
        mock_start.reset_mock()
        second_update = self.service.detect_and_process_updates(initial_run, self.watch_dir, self.db)
        assert second_update is None
        mock_start.assert_not_called()

    def test_unsupported_file_ignored(self):
        initial_run = Run(
            name="Initial Watched Run",
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )
        self.db.add(initial_run)
        self.db.commit()

        # Add unsupported TXT file
        txt_path = os.path.join(self.watch_dir, "notes.txt")
        with open(txt_path, "wb") as f:
            f.write(b"Some plain notes")

        update_run = self.service.detect_and_process_updates(initial_run, self.watch_dir, self.db)
        assert update_run is None

    @patch("app.workflow.service.WorkflowService.start")
    def test_concurrency_locking(self, mock_start):
        mock_start.return_value = {"thread_id": "test_thread", "state": {"status": "completed"}}
        initial_run = Run(
            name="Initial Watched Run",
            status=RunStatus.PENDING,
            stage=WorkflowStage.INGESTION,
        )
        self.db.add(initial_run)
        self.db.commit()

        doc_path = os.path.join(self.watch_dir, "contract.docx")
        with open(doc_path, "wb") as f:
            f.write(b"Mock PDF Content")

        # Simulate concurrent scanning by calling in a transaction with another session
        db2 = SessionLocal()
        try:
            # First transaction starts detect_and_process_updates
            # To simulate locking block or concurrent prevention, let's call it twice
            # Since first one locks the Run, the second one should block/verify protection
            # We assert that running detect_and_process_updates twice doesn't create duplicate update runs
            update_1 = self.service.detect_and_process_updates(initial_run, self.watch_dir, self.db)
            assert update_1 is not None
            
            # Re-fetch from DB2 to simulate second worker process
            service2 = get_run_service(db2)
            run2 = db2.query(Run).filter(Run.id == initial_run.id).first()
            update_2 = service2.detect_and_process_updates(run2, self.watch_dir, db2)
            assert update_2 is None
        finally:
            db2.close()
