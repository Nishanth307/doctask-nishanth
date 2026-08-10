from pathlib import Path


class StorageService:
    """
    Handles saving and retrieving uploaded files.
    """

    def __init__(self, upload_dir: str) -> None:
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def save(self, fileName: str, content: bytes) -> str:
        file_path = self.upload_dir / fileName
        file_path.write_bytes(content)
        return str(file_path)
