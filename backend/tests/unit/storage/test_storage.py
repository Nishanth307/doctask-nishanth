from pathlib import Path
from unittest.mock import MagicMock, patch

from app.storage.factory import get_storage_adapter
from app.storage.gcs import GCSStorageAdapter
from app.storage.local import LocalStorageAdapter
from app.storage.storage import StorageService


class TestStorageService:

    def test_save_file_successfully(self, tmp_path: Path):
        # Arrange
        storage = StorageService(str(tmp_path))

        filename = "contract.pdf"
        content = b"contract content"

        # Act
        file_path = storage.save(
            filename,
            content,
        )

        # Assert
        saved_file = Path(file_path)

        assert saved_file.exists()
        assert saved_file.is_file()
        assert saved_file.read_bytes() == content
        assert saved_file.name == filename

    def test_save_empty_file(self, tmp_path: Path):
        # Arrange
        storage = StorageService(str(tmp_path))

        filename = "empty.txt"
        content = b""

        # Act
        file_path = storage.save(
            filename,
            content,
        )

        # Assert
        saved_file = Path(file_path)

        assert saved_file.exists()
        assert saved_file.read_bytes() == b""

    def test_save_file_with_spaces(self, tmp_path: Path):
        # Arrange
        storage = StorageService(str(tmp_path))

        filename = "employment contract.pdf"
        content = b"contract"

        # Act
        file_path = storage.save(
            filename,
            content,
        )

        # Assert
        saved_file = Path(file_path)

        assert saved_file.exists()
        assert saved_file.name == filename
        assert saved_file.read_bytes() == content

    def test_storage_directory_is_created(
        self,
        tmp_path: Path,
    ):
        # Arrange
        upload_dir = tmp_path / "uploads"

        # Act
        StorageService(str(upload_dir))

        # Assert
        assert upload_dir.exists()
        assert upload_dir.is_dir()


class TestGCSStorageAdapter:

    def test_gcs_save_and_get(self, tmp_path: Path):
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.download_as_bytes.return_value = b"gcs file content"

        gcs_adapter = GCSStorageAdapter(
            bucket_name="test-bucket",
            prefix="test-uploads",
            cache_dir=tmp_path / "cache",
            client=mock_client,
        )

        # Save
        saved_uri = gcs_adapter.save("nda.pdf", b"gcs file content")
        assert saved_uri == "gs://test-bucket/test-uploads/nda.pdf"
        mock_blob.upload_from_string.assert_called_once_with(b"gcs file content")

        # Local path cached
        local_path = gcs_adapter.get_local_path(saved_uri)
        assert local_path.exists()
        assert local_path.read_bytes() == b"gcs file content"

    def test_factory_returns_correct_adapter(self, tmp_path: Path):
        # Default returns LocalStorageAdapter
        local = get_storage_adapter(upload_dir=str(tmp_path))
        assert isinstance(local, LocalStorageAdapter)

        # With bucket specified returns GCSStorageAdapter
        gcs = get_storage_adapter(bucket_name="my-gcs-bucket")
        assert isinstance(gcs, GCSStorageAdapter)
        assert gcs.bucket_name == "my-gcs-bucket"