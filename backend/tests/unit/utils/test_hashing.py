from app.utils.hashing import calculate_sha256

class TestCalculateSha256:

    def test_calculates_hash_correctly(self):
        content = b"hello world"

        #Act 
        result = calculate_sha256(content)

        assert result == (
            "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee"
            "9088f7ace2efcde9"
        )

    def test_same_content_produces_same_hsah(self):
        #Arrange 
        content = b"same content"

        #Act 
        hash_one = calculate_sha256(content)
        hash_two = calculate_sha256(content)

        assert hash_one == hash_two

    def test_different_content_produces_different_hash(self):
        # Arrange
        content_one = b"document one"
        content_two = b"document two"

        # Act
        hash_one = calculate_sha256(content_one)
        hash_two = calculate_sha256(content_two)

        # Assert
        assert hash_one != hash_two

    def test_empty_content(self):
        # Arrange
        content = b""

        # Act
        result = calculate_sha256(content)

        # Assert
        assert len(result) == 64