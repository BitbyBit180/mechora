"""Public RAG orchestration entry point."""

from __future__ import annotations

from typing import Any

from .generator import (
    CitationValidationError,
    OpenRouterGenerator,
    citations_for_sources,
)
from .retriever import Retriever


class RAGError(RuntimeError):
    """Base class for controlled RAG failures surfaced by the API."""


class RAGServiceError(RAGError):
    """Embedding, vector-store, or LLM service failure."""


class RAGCitationError(RAGError):
    """The model response failed citation/schema validation."""


INSUFFICIENT_ANSWER = (
    "The available manuals do not contain sufficient information to answer this question."
)


def answer_question(
    question: str,
    machine_id: str,
    *,
    retriever: Retriever | None = None,
    generator: OpenRouterGenerator | None = None,
) -> dict[str, Any]:
    """Answer a question using only the selected machine's retrieved manuals."""

    question = str(question or "").strip()
    machine_id = str(machine_id or "").strip()
    if not question:
        raise ValueError("question is required")
    if not machine_id:
        raise ValueError("machine_id is required")

    retriever = retriever or Retriever()
    try:
        chunks = retriever.retrieve(question, machine_id)
    except Exception as exc:
        raise RAGServiceError(f"Retrieval failed: {exc}") from exc

    # Layer 1: no surviving evidence means no LLM call at all.
    if not chunks:
        return {"status": "INSUFFICIENT", "answer": INSUFFICIENT_ANSWER, "sources": []}

    generator = generator or OpenRouterGenerator()
    try:
        result = generator.generate(question, chunks, machine_id=machine_id)
        sources = citations_for_sources(result["used_sources"], chunks)
    except CitationValidationError as exc:
        raise RAGCitationError(str(exc)) from exc
    except Exception as exc:
        if isinstance(exc, RAGError):
            raise
        raise RAGServiceError(f"Generation failed: {exc}") from exc
    return {
        "status": result["status"],
        "answer": result["answer"],
        "sources": sources,
    }
