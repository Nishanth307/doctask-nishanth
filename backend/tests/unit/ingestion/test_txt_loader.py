from pathlib import Path

from app.ingestion.loaders.txt import TxtLoader


class TestTxtLoader:

    def test_load_text_file(self, tmp_path: Path):
        # Arrange
        file_path = tmp_path / "notes.txt"
        file_path.write_text(
            "Hello DocTask",
            encoding="utf-8",
        )

        loader = TxtLoader()

        # Act
        result = loader.load(file_path)

        # Assert
        assert result.text == "Hello DocTask"
        assert result.source == str(file_path)
        assert result.metadata["format"] == "txt"

    def test_load_empty_text_file(self, tmp_path: Path):
        # Arrange
        file_path = tmp_path / "empty.txt"
        file_path.write_text(
            "",
            encoding="utf-8",
        )

        loader = TxtLoader()

        # Act
        result = loader.load(file_path)

        # Assert
        assert result.text == ""
        assert result.metadata["format"] == "txt"

    def test_load_unicode_text(self, tmp_path: Path):
        # Arrange
        file_path = tmp_path / "unicode.txt"

        content = "Hello 世界 — नमस्ते"

        file_path.write_text(
            content,
            encoding="utf-8",
        )

        loader = TxtLoader()

        # Act
        result = loader.load(file_path)

        # Assert
        assert result.text == content