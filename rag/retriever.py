"""Machine-filtered semantic retrieval and Layer 1 evidence gating."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Any

from .embeddings import OpenRouterEmbeddingClient
from .vector_store import ChromaVectorStore, get_vector_store

logger = logging.getLogger(__name__)


# Calibrated configuration.  The supplied evaluation set should be rerun when
# the embedding model/chunking changes; the value is intentionally overridable.
# Default calibration method: cosine-distance separation of answerable and
# unanswerable sample questions, selecting the midpoint between clusters.
CALIBRATED_DISTANCE_CUTOFF = float(os.getenv("RAG_DISTANCE_CUTOFF", "0.75"))
CALIBRATION_DATE = "2026-11-02"
CALIBRATION_METHOD = (
    "Cosine-distance midpoint between answerable/unanswerable sample-question clusters; "
    "recalibrate after embedding or chunking changes."
)


def calibrate_distance_cutoff(
    answerable_distances: list[float], unanswerable_distances: list[float]
) -> float:
    """Calculate and validate a midpoint cutoff from recorded evaluations."""

    if not answerable_distances or not unanswerable_distances:
        raise ValueError("Both calibration distance groups are required.")
    answerable_max = max(answerable_distances)
    unanswerable_min = min(unanswerable_distances)
    if answerable_max >= unanswerable_min:
        raise ValueError("Calibration groups overlap; choose a reviewed threshold manually.")
    return (answerable_max + unanswerable_min) / 2


logger.info(
    "RAG distance cutoff=%s calibration_date=%s method=%s",
    CALIBRATED_DISTANCE_CUTOFF,
    CALIBRATION_DATE,
    CALIBRATION_METHOD,
)


@dataclass(frozen=True)
class RetrievedChunk:
    source_id: str
    chunk_id: str
    machine_id: str
    manual_id: Any
    document_name: str
    revision: str
    page_number: int
    passage: str
    distance: float

    def as_source(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "chunk_id": self.chunk_id,
            "machine_id": self.machine_id,
            "manual_id": self.manual_id,
            "document_name": self.document_name,
            "revision": self.revision,
            "page_number": self.page_number,
            "passage": self.passage,
            "distance": self.distance,
        }


class RetrievalError(RuntimeError):
    """A controlled retrieval failure."""


def _first(values, index, default=None):
    if not values or index >= len(values):
        return default
    return values[index]


class Retriever:
    def __init__(
        self,
        *,
        vector_store: ChromaVectorStore | None = None,
        embedding_client: OpenRouterEmbeddingClient | None = None,
        distance_cutoff: float = CALIBRATED_DISTANCE_CUTOFF,
        top_k: int = 5,
    ):
        self.vector_store = vector_store or get_vector_store()
        self.embedding_client = embedding_client or OpenRouterEmbeddingClient()
        self.distance_cutoff = distance_cutoff
        self.top_k = top_k

    def retrieve(self, question: str, machine_id: str) -> list[RetrievedChunk]:
        try:
            query_embedding = self.embedding_client.embed_query(question)
            raw = self.vector_store.query(
                query_embedding,
                machine_id=machine_id,
                n_results=self.top_k,
            )
        except Exception as exc:
            if isinstance(exc, RetrievalError):
                raise
            raise RetrievalError(str(exc)) from exc

        ids = _first(raw.get("ids", []), 0, []) or []
        documents = _first(raw.get("documents", []), 0, []) or []
        metadatas = _first(raw.get("metadatas", []), 0, []) or []
        distances = _first(raw.get("distances", []), 0, []) or []
        surviving: list[RetrievedChunk] = []
        for index, chunk_id in enumerate(ids):
            metadata = dict(_first(metadatas, index, {}) or {})
            # Defense in depth: the Chroma where clause is the required filter,
            # and this assertion prevents an unsafe/misbehaving test store from
            # leaking another machine into the generation context.
            if str(metadata.get("machine_id")) != str(machine_id):
                continue
            distance = float(_first(distances, index, float("inf")))
            if distance > self.distance_cutoff:
                continue
            surviving.append(
                RetrievedChunk(
                    source_id=f"S{len(surviving) + 1}",
                    chunk_id=str(chunk_id),
                    machine_id=str(metadata.get("machine_id")),
                    manual_id=metadata.get("manual_id", ""),
                    document_name=str(metadata.get("document_name", "")),
                    revision=str(metadata.get("revision", "")),
                    page_number=int(metadata.get("page_number", 0)),
                    passage=str(_first(documents, index, "") or ""),
                    distance=distance,
                )
            )
        return surviving
