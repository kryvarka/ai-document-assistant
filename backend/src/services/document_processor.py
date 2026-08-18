import io
from pathlib import Path

import tiktoken
from docx import Document as DocxDocument
from pypdf import PdfReader

from src.config import settings
from src.middleware.error_handler import DocumentProcessingError
from src.middleware.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_PARSERS = {".pdf", ".txt", ".docx", ".md"}
_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def extract_text(file_path: Path, file_content: bytes | None = None) -> str:
    suffix = file_path.suffix.lower()

    if suffix not in SUPPORTED_PARSERS:
        raise DocumentProcessingError(f"Unsupported file type: {suffix}")

    try:
        if suffix == ".pdf":
            return _extract_pdf(file_path, file_content)
        if suffix in (".txt", ".md"):
            return _extract_text_file(file_path, file_content)
        if suffix == ".docx":
            return _extract_docx(file_path, file_content)
    except DocumentProcessingError:
        raise
    except Exception as exc:
        logger.error("text_extraction_failed", file=str(file_path), error=str(exc))
        raise DocumentProcessingError(
            f"Failed to extract text from {file_path.name}: {exc}"
        ) from exc

    raise DocumentProcessingError(f"Unsupported file type: {suffix}")


def _extract_pdf(file_path: Path, file_content: bytes | None) -> str:
    source = io.BytesIO(file_content) if file_content else file_path
    reader = PdfReader(source)
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages)
    if not text.strip():
        raise DocumentProcessingError(f"No extractable text found in {file_path.name}")
    return text


def _extract_text_file(file_path: Path, file_content: bytes | None) -> str:
    if file_content:
        return file_content.decode("utf-8", errors="replace")
    return file_path.read_text(encoding="utf-8", errors="replace")


def _extract_docx(file_path: Path, file_content: bytes | None) -> str:
    source = io.BytesIO(file_content) if file_content else file_path
    doc = DocxDocument(source)
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    text = "\n\n".join(paragraphs)
    if not text.strip():
        raise DocumentProcessingError(f"No extractable text found in {file_path.name}")
    return text


def chunk_text(
    text: str,
    chunk_size: int = settings.chunk_size,
    chunk_overlap: int = settings.chunk_overlap,
) -> list[str]:
    separators = ["\n\n", "\n", ". ", " "]
    return _recursive_split(text, separators, chunk_size, chunk_overlap)


def _recursive_split(
    text: str,
    separators: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    if not text.strip():
        return []

    token_count = count_tokens(text)
    if token_count <= chunk_size:
        return [text.strip()]

    separator = separators[0] if separators else " "
    remaining_separators = separators[1:] if len(separators) > 1 else []
    parts = text.split(separator)

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_tokens = 0

    for part in parts:
        part_tokens = count_tokens(part)

        if part_tokens > chunk_size and remaining_separators:
            if current_chunk:
                chunks.append(separator.join(current_chunk).strip())
                current_chunk = _get_overlap_parts(current_chunk, separator, chunk_overlap)
                current_tokens = count_tokens(separator.join(current_chunk))

            sub_chunks = _recursive_split(part, remaining_separators, chunk_size, chunk_overlap)
            chunks.extend(sub_chunks)
            continue

        if current_tokens + part_tokens + 1 > chunk_size and current_chunk:
            chunks.append(separator.join(current_chunk).strip())
            current_chunk = _get_overlap_parts(current_chunk, separator, chunk_overlap)
            current_tokens = count_tokens(separator.join(current_chunk))

        current_chunk.append(part)
        current_tokens += part_tokens + 1

    if current_chunk:
        final = separator.join(current_chunk).strip()
        if final:
            chunks.append(final)

    return [c for c in chunks if c.strip()]


def _get_overlap_parts(
    parts: list[str],
    separator: str,
    overlap_tokens: int,
) -> list[str]:
    overlap_parts: list[str] = []
    overlap_count = 0

    for part in reversed(parts):
        part_tokens = count_tokens(part)
        if overlap_count + part_tokens > overlap_tokens:
            break
        overlap_parts.insert(0, part)
        overlap_count += part_tokens

    return overlap_parts
