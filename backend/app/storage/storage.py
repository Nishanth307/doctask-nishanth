from pathlib import Path


class StorageService:
    """
    Handles saving and retrieving uploaded files.
    """

    def __init__(self, upload_dir: str) -> None:
        from app.core.config import PROJECT_ROOT
        path = Path(upload_dir)
        if not path.is_absolute():
            self.upload_dir = (PROJECT_ROOT / path).resolve()
        else:
            self.upload_dir = path.resolve()
            
        self.upload_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def save(self, fileName: str, content: bytes) -> str:
        file_path = self.upload_dir / fileName
        file_path.write_bytes(content)
        # Store project-relative path in the database to keep database records stable: e.g. "storage/uploads/..."
        from app.core.config import PROJECT_ROOT
        try:
            relative_path = file_path.relative_to(PROJECT_ROOT)
            return str(relative_path)
        except ValueError:
            return str(file_path)
