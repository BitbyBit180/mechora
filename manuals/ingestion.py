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

        # Keep Django's auditable chunk table in sync with the vector index.
        # Chroma is used for retrieval; this relational copy powers the Admin
        # panel and preserves the exact page/chunk metadata for inspection.
        try:
            from rag.models import RAGDocumentChunk
            from .models import Manual

            manual_record = Manual.objects.filter(pk=manual_id).first()
            if manual_record is not None:
                page_indexes: dict[int, int] = {}
                expected_keys: set[tuple[int, int]] = set()
                for chunk in chunks:
                    page_indexes[chunk.page_number] = page_indexes.get(chunk.page_number, 0) + 1
                    chunk_index = page_indexes[chunk.page_number]
                    expected_keys.add((chunk.page_number, chunk_index))
                    RAGDocumentChunk.objects.update_or_create(
                        manual=manual_record,
                        page_number=chunk.page_number,
                        chunk_index=chunk_index,
                        defaults={
                            "machine": manual_record.machine,
                            "passage_id": chunk.chunk_id,
                            "chunk_text": chunk.text,
                        },
                    )

                # Remove stale rows if a later extraction produces fewer
                # chunks on a page, keeping Admin truthful after re-ingestion.
                for stored in RAGDocumentChunk.objects.filter(manual=manual_record):
                    if (stored.page_number, stored.chunk_index) not in expected_keys:
                        stored.delete()
        except Exception as exc:
            raise IngestionError(f"Unable to persist Django chunk records: {exc}") from exc

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
