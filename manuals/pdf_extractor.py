"""Page-wise extraction of manufacturing manuals.

This module deliberately knows nothing about Django models.  The caller passes
the registration metadata that must travel with every extracted page.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Union


class PDFExtractionError(RuntimeError):
    """Raised when a PDF cannot be opened or read."""


@dataclass(frozen=True)
class ExtractedPage:
    machine_id: str
    manual_id: Union[int, str]
    document_name: str
    revision: str
    page_number: int
    text: str


def extract_pages(
    pdf_path: Union[str, Path],
    *,
    machine_id: str,
    manual_id: Union[int, str],
    document_name: str | None = None,
    revision: str = "",
) -> list[ExtractedPage]:
    """Extract non-empty pages from *pdf_path* using PyMuPDF.

    PDF page numbers are one-based.  Pages with fewer than 20 non-whitespace
    characters are intentionally omitted, while their original page number is
    retained on all subsequent pages.
    """

    try:
        import pymupdf as fitz  # type: ignore
    except ImportError:
        try:
            import fitz  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on deployment env
            raise PDFExtractionError(
                "PyMuPDF is required for manual ingestion; install package 'pymupdf'."
            ) from exc

    path = Path(pdf_path)
    if document_name is None:
        document_name = path.name

    try:
        document = fitz.open(str(path))
    except Exception as exc:  # fitz raises several version-specific exceptions
        raise PDFExtractionError(f"Unable to open PDF '{path.name}': {exc}") from exc

    pages: list[ExtractedPage] = []
    try:
        for index, page in enumerate(document):
            try:
                text = page.get_text("text") or ""
            except Exception as exc:
                raise PDFExtractionError(
                    f"Unable to extract page {index + 1} from '{path.name}': {exc}"
                ) from exc
            cleaned = text.strip()
            if len(cleaned) < 20:
                continue
            pages.append(
                ExtractedPage(
                    machine_id=machine_id,
                    manual_id=manual_id,
                    document_name=document_name,
                    revision=revision,
                    page_number=index + 1,
                    text=cleaned,
                )
            )
    finally:
        document.close()
    return pages


# A descriptive alias makes the API convenient for callers that prefer the
# longer name used in the PRD.
extract_pdf_pages = extract_pages
