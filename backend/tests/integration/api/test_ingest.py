from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


import pytest
from sqlalchemy import text
from app.core.database import SessionLocal

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    db = SessionLocal()
    try:
        db.execute(text("TRUNCATE TABLE documents CASCADE"))
        db.execute(text("TRUNCATE TABLE runs CASCADE"))
        db.commit()
    finally:
        db.close()


class TestDocumentIngestionAPI:

    def create_run(self) -> str:
        response = client.post(
            "/api/v1/runs",
            json={"name": "Document Test Run"},
        )

        assert response.status_code == 201

        return response.json()["id"]

    def test_upload_pdf_successfully(self):
        # Arrange
        run_id = self.create_run()

        content = b"sample pdf content"

        files = {
            "file": (
                "contract.pdf",
                BytesIO(content),
                "application/pdf",
            )
        }

        # Act
        response = client.post(
            f"/api/v1/runs/{run_id}/documents",
            files=files,
        )

        # Assert
        assert response.status_code == 201

        body = response.json()

        assert body["run_id"] == run_id
        assert body["filename"] == "contract.pdf"
        assert body["file_type"] == ".pdf"
        assert body["checksum"] is not None

    def test_upload_docx_successfully(self):
        # Arrange
        run_id = self.create_run()

        files = {
            "file": (
                "contract.docx",
                BytesIO(b"docx content"),
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document",
            )
        }

        # Act
        response = client.post(
            f"/api/v1/runs/{run_id}/documents",
            files=files,
        )

        # Assert
        assert response.status_code == 201

        body = response.json()

        assert body["filename"] == "contract.docx"
        assert body["file_type"] == ".docx"

    def test_upload_txt_successfully(self):
        # Arrange
        run_id = self.create_run()

        files = {
            "file": (
                "notes.txt",
                BytesIO(b"plain text document"),
                "text/plain",
            )
        }

        # Act
        response = client.post(
            f"/api/v1/runs/{run_id}/documents",
            files=files,
        )

        # Assert
        assert response.status_code == 201

        body = response.json()

        assert body["filename"] == "notes.txt"
        assert body["file_type"] == ".txt"

    def test_upload_to_non_existing_run(self):
        # Arrange
        run_id = uuid4()

        files = {
            "file": (
                "contract.pdf",
                BytesIO(b"contract"),
                "application/pdf",
            )
        }

        # Act
        response = client.post(
            f"/api/v1/runs/{run_id}/documents",
            files=files,
        )

        # Assert
        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"

    def test_upload_unsupported_file(self):
        # Arrange
        run_id = self.create_run()

        files = {
            "file": (
                "malware.exe",
                BytesIO(b"not allowed"),
                "application/octet-stream",
            )
        }

        # Act
        response = client.post(
            f"/api/v1/runs/{run_id}/documents",
            files=files,
        )

        # Assert
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_upload_duplicate_document(self):
        # Arrange
        run_id = self.create_run()

        content = b"same document"

        files = {
            "file": (
                "contract.pdf",
                BytesIO(content),
                "application/pdf",
            )
        }

        first_response = client.post(
            f"/api/v1/runs/{run_id}/documents",
            files=files,
        )

        assert first_response.status_code == 201

        # Act
        files = {
            "file": (
                "another-name.pdf",
                BytesIO(content),
                "application/pdf",
            )
        }

        second_response = client.post(
            f"/api/v1/runs/{run_id}/documents",
            files=files,
        )

        # Assert
        assert second_response.status_code == 400
        assert (
            second_response.json()["detail"]
            == "Document already exists"
        )

    def test_upload_empty_file(self):
        # Arrange
        run_id = self.create_run()

        files = {
            "file": (
                "empty.txt",
                BytesIO(b""),
                "text/plain",
            )
        }

        # Act
        response = client.post(
            f"/api/v1/runs/{run_id}/documents",
            files=files,
        )

        # Assert
        assert response.status_code == 201

    def test_upload_without_file(self):
        # Arrange
        run_id = self.create_run()

        # Act
        response = client.post(
            f"/api/v1/runs/{run_id}/documents",
        )

        # Assert
        assert response.status_code == 422

    def test_upload_uppercase_extension(self):
        # Arrange
        run_id = self.create_run()

        files = {
            "file": (
                "CONTRACT.PDF",
                BytesIO(b"contract"),
                "application/pdf",
            )
        }

        # Act
        response = client.post(
            f"/api/v1/runs/{run_id}/documents",
            files=files,
        )

        # Assert
        assert response.status_code == 201
        assert response.json()["file_type"] == ".pdf"