"""Manual ingestion orchestration: extract -> chunk -> embed -> upsert."""

from __future__ import annotations

from pathlib import Path
from typing import Union

from .chunker import ManualChunk, chunk_pages
from .pdf_extractor import extract_pages


class IngestionError(RuntimeError):
    """Raised when a manual cannot be completely ingested."""


def ingest_manual(
    pdf_path: str | Path,
    *,
    machine_id: str,
    manual_id: Union[int, str],
    document_name: str | None = None,
    revision: str = "",
    vector_store=None,
    embedding_client=None,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> dict:
    """Ingest a manual idempotently and return ingestion statistics.

    Existing deterministic IDs are not embedded again.  ``upsert`` is still
    used for every record, making the operation safe to repeat and allowing
    corrected text/metadata to replace an earlier record with the same ID.
    """

    try:
        pages = extract_pages(
            pdf_path,
            machine_id=machine_id,
            manual_id=manual_id,
            document_name=document_name,
            revision=revision,
        )
        chunks = chunk_pages(
            pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        if not chunks:
            raise IngestionError("The PDF contains no extractable manual text.")

        if vector_store is None:
            from rag.vector_store import get_vector_store

            vector_store = get_vector_store()
        if embedding_client is None:
            from rag.embeddings import OpenRouterEmbeddingClient

            embedding_client = OpenRouterEmbeddingClient()

        existing = set(vector_store.existing_ids([chunk.chunk_id for chunk in chunks]))
        new_chunks = [chunk for chunk in chunks if chunk.chunk_id not in existing]
        embeddings = (
            embedding_client.embed_documents([chunk.text for chunk in new_chunks])
            if new_chunks
            else []
        )
        if len(embeddings) != len(new_chunks):
            raise IngestionError("Embedding service returned an incomplete batch.")

        records = []
        for chunk, embedding in zip(new_chunks, embeddings):
            records.append((chunk, embedding))
        # Existing deterministic IDs are already present; only new records
        # need an upsert and only new records needed embedding API calls.
        if records:
            vector_store.upsert_chunks(records)

        return {
            "status": "complete",
            "pages_extracted": len(pages),
            "chunks_created": len(new_chunks),
            "chunks_total": len(chunks),
        }
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(f"Manual ingestion failed: {exc}") from exc


ingest_pdf = ingest_manual
