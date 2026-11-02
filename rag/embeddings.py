"""OpenRouter embeddings with separate document/query input types and retries."""

from __future__ import annotations

import os
import time
from typing import Iterable

from .openrouter import OpenRouterClient, OpenRouterError


DOCUMENT_INPUT_TYPE = "search_document"
QUERY_INPUT_TYPE = "search_query"
EMBEDDING_MODEL = os.getenv(
    "OPENROUTER_EMBEDDING_MODEL", "nvidia/nemotron-3-embed-1b:free"
)


class EmbeddingAPIError(RuntimeError):
    """A controlled embedding-service failure."""


class OpenRouterEmbeddingClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = EMBEDDING_MODEL,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
        client: OpenRouterClient | None = None,
    ):
        self.model = model
        self.max_retries = max(0, max_retries)
        self.backoff_seconds = backoff_seconds
        self._client = client or OpenRouterClient(api_key=api_key)

    def _embed_once(self, texts: list[str], input_type: str) -> list[list[float]]:
        try:
            response = self._client.post(
                "/embeddings",
                {
                    "model": self.model,
                    "input": texts,
                    "input_type": input_type,
                },
            )
        except OpenRouterError as exc:
            raise EmbeddingAPIError(str(exc)) from exc
        items = response.get("data")
        if not isinstance(items, list):
            raise EmbeddingAPIError("OpenRouter returned no embedding data.")
        try:
            ordered = sorted(items, key=lambda item: int(item.get("index", 0)))
            vectors = [list(item["embedding"]) for item in ordered]
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingAPIError("OpenRouter returned invalid embeddings.") from exc
        if len(vectors) != len(texts) or any(not vector for vector in vectors):
            raise EmbeddingAPIError("OpenRouter returned an incomplete embedding batch.")
        return vectors

    def embed(self, texts: Iterable[str], *, input_type: str) -> list[list[float]]:
        values = [str(text) for text in texts]
        if not values:
            return []
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return self._embed_once(values, input_type)
            except EmbeddingAPIError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(self.backoff_seconds * (2**attempt))
        raise EmbeddingAPIError(f"OpenRouter embedding request failed: {last_error}") from last_error

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        return self.embed(texts, input_type=DOCUMENT_INPUT_TYPE)

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text], input_type=QUERY_INPUT_TYPE)[0]


# Backwards-compatible names for code that imported the earlier Gemini class.
GeminiEmbeddingClient = OpenRouterEmbeddingClient
DOCUMENT_TASK = DOCUMENT_INPUT_TYPE
QUESTION_TASK = QUERY_INPUT_TYPE
