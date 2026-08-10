from pathlib import Path

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