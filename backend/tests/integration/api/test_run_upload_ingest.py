import os
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings, PROJECT_ROOT
from app.core.database import SessionLocal
from app.persistence.models.run import Run
from app.persistence.models.document import Document
from app.persistence.models.document_chunk import DocumentChunkModel
from app.api.routes_ingest import get_document_service
from app.services.run_service import RunService
from app.persistence.repositories.run import RunRepository
from app.main import app

class TestRunUploadIngestRegression:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.db = SessionLocal()
        self.run_repo = RunRepository(self.db)
        self.run_service = RunService(self.run_repo)
        self.doc_service = get_document_service(self.db)
        self.client = TestClient(app)

        yield

        # Teardown database records
        self.db.query(DocumentChunkModel).delete()
        self.db.query(Document).delete()
        self.db.query(Run).delete()
        self.db.commit()
        self.db.close()

    def test_docx_and_pdf_multipart_ingestion(self):
        pdf_bytes = b"%PDF-1.4 mock content"
        
        from app.ingestion.loaders.docx import DocxLoader
        from app.ingestion.loaders.pdf import PdfLoader
        from app.ingestion.loaders.base import LoadedDocument

        original_docx_load = DocxLoader.load
        original_pdf_load = PdfLoader.load

        DocxLoader.load = MagicMock(return_value=LoadedDocument(
            text="Mocked DOCX Text Content",
            source="mock_docx",
            metadata={"format": "docx"}
        ))
        PdfLoader.load = MagicMock(return_value=LoadedDocument(
            text="Mocked PDF Text Content",
            source="mock_pdf",
            metadata={"format": "pdf"}
        ))

        try:
            # 2. Run Create Run request
            payload = {"name": "Acme Vendor Contract Review"}
            files = [
                ("files", ("acme_master_service_agreement.pdf", pdf_bytes, "application/pdf")),
                ("files", ("acme_statement_of_work.docx", b"mock docx bytes", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
                ("rules_file", ("contract_review_checklist.pdf", pdf_bytes + b"different rules content", "application/pdf"))
            ]

            response = self.client.post("/api/v1/runs", data=payload, files=files)
            assert response.status_code == 201
            
            run_data = response.json()
            run_id = run_data["id"]

            # 3. Verify files physically exist at the canonical storage locations
            upload_dir = settings.absolute_upload_dir
            assert upload_dir.exists()
            
            pdf_path = upload_dir / "acme_master_service_agreement.pdf"
            docx_path = upload_dir / "acme_statement_of_work.docx"
            rules_path = upload_dir / "contract_review_checklist.pdf"

            assert pdf_path.exists()
            assert docx_path.exists()
            assert rules_path.exists()

            # 4. Verify document records exist in the database with project-relative paths
            docs = self.db.query(Document).filter(Document.run_id == run_id).all()
            assert len(docs) == 3
            
            paths = [d.file_path for d in docs]
            assert "storage/uploads/acme_master_service_agreement.pdf" in paths
            assert "storage/uploads/acme_statement_of_work.docx" in paths
            assert "storage/uploads/contract_review_checklist.pdf" in paths

            # 5. Verify chunk creation
            chunks = self.db.query(DocumentChunkModel).all()
            assert len(chunks) > 0

        finally:
            # Restore loaders
            DocxLoader.load = original_docx_load
            PdfLoader.load = original_pdf_load
