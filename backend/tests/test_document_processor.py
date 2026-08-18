from pathlib import Path

import pytest

from src.services.document_processor import chunk_text, extract_text


class TestExtractText:
    def test_extract_txt_from_bytes(self, tmp_path):
        content = b"Hello, this is a test document."
        file_path = Path("test.txt")
        result = extract_text(file_path, file_content=content)
        assert result == "Hello, this is a test document."

    def test_extract_txt_from_file(self, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("File content here.")
        result = extract_text(file_path)
        assert result == "File content here."

    def test_extract_md_from_bytes(self):
        content = b"# Heading\n\nSome markdown content."
        file_path = Path("test.md")
        result = extract_text(file_path, file_content=content)
        assert "# Heading" in result

    def test_unsupported_extension_raises(self):
        with pytest.raises(Exception, match="Unsupported file type"):
            extract_text(Path("test.xyz"))


class TestChunkText:
    def test_short_text_not_split(self, sample_short_text):
        chunks = chunk_text(sample_short_text, chunk_size=500, chunk_overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == sample_short_text

    def test_empty_text_returns_empty(self):
        chunks = chunk_text("", chunk_size=500, chunk_overlap=50)
        assert chunks == []

    def test_whitespace_only_returns_empty(self):
        chunks = chunk_text("   \n\n  ", chunk_size=500, chunk_overlap=50)
        assert chunks == []

    def test_long_text_produces_multiple_chunks(self, sample_long_text):
        chunks = chunk_text(sample_long_text, chunk_size=100, chunk_overlap=10)
        assert len(chunks) > 1

    def test_chunks_contain_all_content(self, sample_multiline_text):
        chunks = chunk_text(sample_multiline_text, chunk_size=50, chunk_overlap=5)
        combined = " ".join(chunks)
        assert "First section" in combined
        assert "Second section" in combined
        assert "Third section" in combined

    def test_no_empty_chunks(self, sample_long_text):
        chunks = chunk_text(sample_long_text, chunk_size=100, chunk_overlap=10)
        for chunk in chunks:
            assert chunk.strip() != ""

    def test_chunk_size_parameter_respected(self, sample_long_text):
        small_chunks = chunk_text(sample_long_text, chunk_size=50, chunk_overlap=5)
        large_chunks = chunk_text(sample_long_text, chunk_size=200, chunk_overlap=20)
        assert len(small_chunks) > len(large_chunks)
