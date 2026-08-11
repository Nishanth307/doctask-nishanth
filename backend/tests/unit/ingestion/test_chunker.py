import pytest

from app.ingestion.chunker import TextChunker, TextChunk


class TestTextChunker:

    def test_empty_text_returns_empty_list(self):
        # Arrange
        chunker = TextChunker()

        # Act
        result = chunker.split("")

        # Assert
        assert result == []

    def test_whitespace_returns_empty_list(self):
        # Arrange
        chunker = TextChunker()

        # Act
        result = chunker.split("   \n\t  ")

        # Assert
        assert result == []

    def test_small_text_creates_single_chunk(self):
        # Arrange
        chunker = TextChunker(
            chunk_size=100,
            chunk_overlap=10,
        )

        # Act
        result = chunker.split("Hello world")

        # Assert
        assert len(result) == 1
        assert result[0].index == 0
        assert result[0].text == "Hello world"

    def test_large_text_creates_multiple_chunks(self):
        # Arrange
        chunker = TextChunker(
            chunk_size=10,
            chunk_overlap=2,
        )

        text = "abcdefghijklmnopqrst"

        # Act
        result = chunker.split(text)

        # Assert
        assert len(result) == 3

        assert result[0].index == 0
        assert result[1].index == 1
        assert result[2].index == 2

    def test_chunks_have_expected_overlap(self):
        # Arrange
        chunker = TextChunker(
            chunk_size=10,
            chunk_overlap=2,
        )

        text = "abcdefghijklmnopqrst"

        # Act
        result = chunker.split(text)

        # Assert
        assert result[0].text == "abcdefghij"
        assert result[1].text == "ijklmnopqr"
        assert result[2].text == "qrst"

    def test_indexes_are_sequential(self):
        # Arrange
        chunker = TextChunker(
            chunk_size=5,
            chunk_overlap=1,
        )

        # Act
        result = chunker.split("abcdefghijklmnop")

        # Assert
        assert [chunk.index for chunk in result] == [0, 1, 2, 3]

    def test_invalid_chunk_size(self):
        with pytest.raises(
            ValueError,
            match="chunk_size",
        ):
            TextChunker(chunk_size=0)

    def test_negative_overlap(self):
        with pytest.raises(
            ValueError,
            match="chunk_overlap",
        ):
            TextChunker(
                chunk_size=100,
                chunk_overlap=-1,
            )

    def test_overlap_cannot_equal_chunk_size(self):
        with pytest.raises(
            ValueError,
            match="smaller than chunk_size",
        ):
            TextChunker(
                chunk_size=100,
                chunk_overlap=100,
            )

    def test_overlap_cannot_exceed_chunk_size(self):
        with pytest.raises(
            ValueError,
            match="smaller than chunk_size",
        ):
            TextChunker(
                chunk_size=100,
                chunk_overlap=101,
            )