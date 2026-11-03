"""Small ChromaDB adapter used by ingestion and retrieval."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


COLLECTION_NAME = "manufacturing_manuals"


class VectorStoreError(RuntimeError):
    """A controlled vector-store failure."""


def _default_path() -> str:
    configured = os.getenv("CHROMA_PERSIST_DIRECTORY")
    if configured:
        return configured
    try:
        from django.conf import settings

        return str(Path(settings.BASE_DIR) / "chroma_db")
    except Exception:
        return str(Path.cwd() / "chroma_db")


class ChromaVectorStore:
    def __init__(self, *, path: str | None = None, collection=None):
        self.path = path or _default_path()
        self._collection = collection

    @property
    def collection(self):
        if self._collection is None:
            try:
                import chromadb  # type: ignore
            except ImportError as exc:  # pragma: no cover
                raise VectorStoreError(
                    "ChromaDB is unavailable; install package 'chromadb'."
                ) from exc
            try:
                Path(self.path).mkdir(parents=True, exist_ok=True)
                client = chromadb.PersistentClient(path=self.path)
                self._collection = client.get_or_create_collection(
                    name=COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as exc:
                raise VectorStoreError(f"Unable to open ChromaDB: {exc}") from exc
        return self._collection

    def existing_ids(self, ids: Iterable[str]) -> list[str]:
        values = list(ids)
        if not values:
            return []
        try:
            result = self.collection.get(ids=values, include=[])
        except Exception:
            # Some Chroma versions reject an empty include list.
            result = self.collection.get(ids=values)
        return list(result.get("ids") or [])

    def upsert_chunks(self, records: Iterable[tuple[object, list[float]]]) -> None:
        records = list(records)
        if not records:
            return
        ids, documents, embeddings, metadatas = [], [], [], []
        for chunk, embedding in records:
            ids.append(chunk.chunk_id)
            documents.append(chunk.text)
            embeddings.append(embedding)
            metadatas.append(
                {
                    "machine_id": chunk.machine_id,
                    "manual_id": chunk.manual_id,
                    "document_name": chunk.document_name,
                    "revision": chunk.revision,
                    "page_number": int(chunk.page_number),
                }
            )
        try:
            self.collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        except Exception as exc:
            raise VectorStoreError(f"Unable to upsert manual chunks: {exc}") from exc

    def query(
        self,
        embedding: list[float],
        *,
        machine_id: str,
        n_results: int = 5,
        where: dict | None = None,
    ) -> dict:
        """Query with the machine filter passed into Chroma itself."""

        try:
            filters = {"machine_id": machine_id}
            if where:
                filters = {"$and": [filters, where]}
            return self.collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
                where=filters,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise VectorStoreError(f"Unable to query manual chunks: {exc}") from exc

    def get_by_ids(self, ids: Iterable[str]) -> dict:
        try:
            return self.collection.get(ids=list(ids), include=["documents", "metadatas"])
        except Exception as exc:
            raise VectorStoreError(f"Unable to resolve citation sources: {exc}") from exc


def get_vector_store() -> ChromaVectorStore:
    return ChromaVectorStore()
