"""Deterministic, page-bounded manual chunking."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable, Union

from .pdf_extractor import ExtractedPage


DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100


@dataclass(frozen=True)
class ManualChunk:
    chunk_id: str
    machine_id: str
    manual_id: Union[int, str]
    document_name: str
    revision: str
    page_number: int
    text: str

    def as_dict(self) -> dict:
        return asdict(self)


def _safe_id(value: object) -> str:
    value = str(value)
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return value or "manual"


def _words(text: str) -> list[str]:
    # Whitespace tokens are predictable, fast, and adequate for the PRD's
    # approximate token-size requirement without introducing a local model.
    return re.findall(r"\S+", text)


def chunk_pages(
    pages: Iterable[ExtractedPage],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[ManualChunk]:
    """Chunk each page independently; no chunk ever crosses a PDF page."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")

    chunks: list[ManualChunk] = []
    for page in pages:
        words = _words(page.text)
        if not words:
            continue
        step = chunk_size - chunk_overlap
        start = 0
        chunk_number = 1
        document_key = (
            f"{_safe_id(page.machine_id)}_{_safe_id(page.manual_id)}_"
            f"{_safe_id(page.document_name)}_{_safe_id(page.revision)}"
        )
        while start < len(words):
            selected = words[start : start + chunk_size]
            text = " ".join(selected).strip()
            if text:
                chunks.append(
                    ManualChunk(
                        chunk_id=(
                            f"{document_key}_P{page.page_number:03d}_C{chunk_number:03d}"
                        ),
                        machine_id=page.machine_id,
                        manual_id=page.manual_id,
                        document_name=page.document_name,
                        revision=page.revision,
                        page_number=page.page_number,
                        text=text,
                    )
                )
            if start + chunk_size >= len(words):
                break
            start += step
            chunk_number += 1
    return chunks


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Return text-only chunks for callers that do not need page metadata."""

    words = _words(text)
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")
    step = chunk_size - chunk_overlap
    result = []
    start = 0
    while start < len(words):
        result.append(" ".join(words[start : start + chunk_size]))
        if start + chunk_size >= len(words):
            break
        start += step
    return result
