"""
document_loader.py

Extracts plain text from uploaded documents (PDF, DOCX, TXT) and splits
that text into overlapping chunks ready for embedding.

Kept intentionally small and dependency-light so it is easy to follow:
    extract_text(path, file_type)  -> full document text
    chunk_text(text)               -> list of chunk strings
"""

from typing import List

from pypdf import PdfReader
from docx import Document as DocxDocument

# Recommended chunk size/overlap from the project requirements.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def extract_text(file_path: str, file_type: str) -> str:
    """Read a PDF, DOCX, or TXT file from disk and return its full text.

    Raises ValueError for unsupported types or files that yield no text,
    so the caller can turn this into a friendly API error.
    """
    file_type = (file_type or "").lower().lstrip(".")

    if file_type == "pdf":
        text = _extract_pdf_text(file_path)
    elif file_type == "docx":
        text = _extract_docx_text(file_path)
    elif file_type == "txt":
        text = _extract_txt_text(file_path)
    else:
        raise ValueError(f"Unsupported document type: {file_type}")

    text = text.strip()
    if not text:
        raise ValueError("No readable text could be found in this document.")

    return text


def _extract_pdf_text(file_path: str) -> str:
    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages.append(page_text)
    return "\n".join(pages)


def _extract_docx_text(file_path: str) -> str:
    document = DocxDocument(file_path)
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    return "\n".join(paragraphs)


def _extract_txt_text(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
        return file.read()


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """Split text into overlapping fixed-size chunks.

    A simple sliding window over characters. Overlap keeps context from
    being cut off awkwardly at chunk boundaries.
    """
    text = " ".join(text.split())  # normalize whitespace

    if not text:
        return []

    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap.")

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        start = end - overlap

    return chunks