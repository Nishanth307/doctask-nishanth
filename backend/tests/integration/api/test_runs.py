from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app


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