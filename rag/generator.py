"""Grounded OpenRouter chat generation and strict citation validation."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from .openrouter import OpenRouterClient, OpenRouterError
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .retriever import RetrievedChunk


LLM_MODEL = os.getenv("OPENROUTER_LLM_MODEL", "liquid/lfm-2.5-2.6b:free")
LLM_FALLBACK_MODELS = tuple(
    model.strip()
    for model in os.getenv("OPENROUTER_LLM_FALLBACK_MODELS", "openrouter/free").split(",")
    if model.strip()
)


class LLMAPIError(RuntimeError):
    """A controlled LLM-service failure."""


class CitationValidationError(ValueError):
    """Raised when an LLM response contains untrusted source references."""


def _response_text(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMAPIError("OpenRouter returned no chat completion content.") from exc
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    raise LLMAPIError("OpenRouter returned an invalid completion content value.")


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise CitationValidationError("OpenRouter returned malformed JSON.") from exc
    if not isinstance(value, dict):
        raise CitationValidationError("LLM response must be a JSON object.")
    return value


def validate_response(
    response: dict[str, Any],
    retrieved_chunks: list[RetrievedChunk],
    *,
    machine_id: str | None = None,
) -> dict[str, Any]:
    """Validate the model result against the current trusted retrieval set."""

    if response.get("status") not in {"ANSWERED", "INSUFFICIENT"}:
        raise CitationValidationError("Invalid answer status from the LLM.")
    answer = response.get("answer")
    used_sources = response.get("used_sources")
    if not isinstance(answer, str) or not answer.strip():
        raise CitationValidationError("LLM response has no answer text.")
    if not isinstance(used_sources, list) or not all(
        isinstance(source_id, str) for source_id in used_sources
    ):
        raise CitationValidationError("used_sources must be a list of source IDs.")

    source_map = {chunk.source_id: chunk for chunk in retrieved_chunks}
    inline_sources = re.findall(r"\[(S\d+)\]", answer)
    for source_id in inline_sources:
        if source_id not in source_map:
            raise CitationValidationError(f"Fabricated or unavailable source ID: {source_id}")
        if source_id not in used_sources:
            raise CitationValidationError(
                f"Inline source {source_id} is missing from used_sources."
            )
    for source_id in used_sources:
        chunk = source_map.get(source_id)
        if chunk is None:
            raise CitationValidationError(f"Fabricated or unavailable source ID: {source_id}")
        if machine_id is not None and chunk.machine_id != str(machine_id):
            raise CitationValidationError(f"Source {source_id} belongs to another machine.")

    if response["status"] == "INSUFFICIENT":
        if used_sources:
            raise CitationValidationError("INSUFFICIENT responses cannot cite sources.")
    else:
        if not used_sources:
            raise CitationValidationError("ANSWERED responses must cite at least one source.")
        missing_inline = [
            source_id for source_id in used_sources if f"[{source_id}]" not in answer
        ]
        if missing_inline:
            # The source IDs have already been validated against the current
            # retrieval result. Some small/free models return the correct
            # used_sources list but omit the inline markers, so add only those
            # trusted IDs server-side rather than rejecting a grounded answer.
            answer = f"{answer.rstrip()} {' '.join(f'[{source_id}]' for source_id in missing_inline)}"

    return {
        "status": response["status"],
        "answer": answer.strip(),
        "used_sources": list(dict.fromkeys(used_sources)),
    }


def citations_for_sources(
    used_sources: list[str], retrieved_chunks: list[RetrievedChunk]
) -> list[dict[str, Any]]:
    """Resolve public citation fields only from trusted retrieved metadata."""

    source_map = {chunk.source_id: chunk for chunk in retrieved_chunks}
    citations = []
    for source_id in used_sources:
        chunk = source_map.get(source_id)
        if chunk is None:
            raise CitationValidationError(f"Unknown source ID: {source_id}")
        citations.append(
            {
                "source_id": chunk.source_id,
                "chunk_id": chunk.chunk_id,
                "manual_id": chunk.manual_id,
                "document_name": chunk.document_name,
                "revision": chunk.revision,
                "page_number": chunk.page_number,
                "passage": chunk.passage,
                "pdf_url": f"/api/manuals/{chunk.manual_id}/pdf/#page={chunk.page_number}",
            }
        )
    return citations


class OpenRouterGenerator:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = LLM_MODEL,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
        fallback_models: tuple[str, ...] = LLM_FALLBACK_MODELS,
        client: OpenRouterClient | None = None,
    ):
        self.model = model
        self.max_retries = max(0, max_retries)
        self.backoff_seconds = backoff_seconds
        self.fallback_models = tuple(
            model for model in fallback_models if model and model != self.model
        )
        self._client = client or OpenRouterClient(api_key=api_key)

    def _generate_once(self, question: str, chunks: list[RetrievedChunk]) -> dict:
        try:
            payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_user_prompt(question, chunks)},
                    ],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                }
            if self.fallback_models:
                payload["models"] = list(self.fallback_models)
            response = self._client.post("/chat/completions", payload)
        except OpenRouterError as exc:
            raise LLMAPIError(str(exc)) from exc
        return parse_json_response(_response_text(response))

    def generate(self, question: str, chunks: list[RetrievedChunk], *, machine_id: str) -> dict:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                raw = self._generate_once(question, chunks)
                return validate_response(raw, chunks, machine_id=machine_id)
            except CitationValidationError:
                raise
            except LLMAPIError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(self.backoff_seconds * (2**attempt))
        raise LLMAPIError(f"OpenRouter generation request failed: {last_error}") from last_error


# Backwards-compatible name for code that imported the earlier Gemini class.
GeminiGenerator = OpenRouterGenerator
