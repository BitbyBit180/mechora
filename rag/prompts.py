"""Prompts for grounded, structured OpenRouter generation."""

from __future__ import annotations

from .retriever import RetrievedChunk


SYSTEM_PROMPT = """You are the Manufacturing Manual Assistant.
Answer only from the supplied manual passages. Do not use general knowledge,
the internet, assumptions, or information not present in the passages.
If the passages do not directly support an answer, return INSUFFICIENT.
Return JSON only with exactly these keys: status, answer, used_sources.
status must be ANSWERED or INSUFFICIENT. used_sources must contain only source
IDs from the context, such as S1. Every source used in the answer must be cited
inline in the answer as [Sx]. Never invent document names, revisions, pages, or
source IDs; the server resolves citation metadata from retrieved records.
"""


def build_context(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for chunk in chunks:
        blocks.append(
            f"[{chunk.source_id}]\n\n"
            f"Document: {chunk.document_name}\n"
            f"Revision: {chunk.revision}\n"
            f"Page: {chunk.page_number}\n\n"
            f"Passage:\n{chunk.passage}"
        )
    return "\n\n".join(blocks)


def build_user_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    return (
        f"Question: {question}\n\n"
        "Retrieved manual context:\n"
        f"{build_context(chunks)}\n\n"
        "Return the required JSON response now."
    )
