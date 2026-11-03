"""Round 3 quality-incident workflow and product-scoped SOP evidence."""

from __future__ import annotations

import csv
import os
import time
import json
from pathlib import Path
from typing import Any

from django.conf import settings

from manuals.pdf_extractor import extract_pages
from rag.models import RAGDocumentChunk
from rag.openrouter import OpenRouterClient
from rag.retriever import Retriever


PACK_ROOT = Path(settings.BASE_DIR) / "Round 3 Student Pack"
MAPPING_PATH = PACK_ROOT / "product_sop_mapping.csv"


class EvidenceError(RuntimeError):
    pass


class IncidentEligibilityError(ValueError):
    pass


def mapped_sops(product_id: str) -> list[dict[str, str]]:
    """Return the authoritative, exact product mapping from the supplied CSV."""
    if not MAPPING_PATH.is_file():
        raise EvidenceError("The product-to-SOP mapping file is unavailable.")
    with MAPPING_PATH.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("product_id") == product_id]
    rows = [row for row in rows if str(row.get("required", "")).lower() == "true"]
    if not rows:
        raise EvidenceError(f"No required SOP mapping exists for product {product_id}.")
    required = {"document_id", "revision", "pdf_filename"}
    if any(not required.issubset(row) or any(not row.get(field, "").strip() for field in required) for row in rows):
        raise EvidenceError(f"The SOP mapping for {product_id} is incomplete.")
    return rows


def _source_link(document_id: str, page_number: int) -> str:
    return f"/api/inspections/incidents/sources/{document_id}/pdf/#page={page_number}"


def _trusted_sources(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate page evidence and assign server-controlled source IDs."""
    sources = []
    seen = set()
    for page in pages:
        key = (page["document_id"], page["revision"], page["page_number"])
        if key in seen:
            continue
        seen.add(key)
        sources.append({**page, "source_id": f"S{len(sources) + 1}"})
    return sources


def _parse_llm_json(content: Any) -> dict[str, Any]:
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not isinstance(content, str):
        raise EvidenceError("Incident generation returned invalid content.")
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EvidenceError("Incident generation returned malformed JSON.") from exc
    if not isinstance(value, dict):
        raise EvidenceError("Incident generation returned an invalid object.")
    return value


def generate_incident_content(inspection, pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate incident content from trusted RAG evidence only."""
    sources = _trusted_sources(pages)
    if not sources:
        raise EvidenceError("No trusted SOP passages were available for generation.")
    source_prompt = "\n\n".join(
        f"[{source['source_id']}] {source['document_id']} | {source['document_name']} | "
        f"revision {source['revision']} | PDF page {source['page_number']}\n{source['passage']}"
        for source in sources
    )
    prompt = f"""Create a factual quality incident response for this saved inspection.

Inspection ID: {inspection.inspection_id}
Product ID: {inspection.product.product_code}
Original model prediction: {inspection.predicted_class}
Model version: {inspection.model_version or 'not recorded'}
Confidence: {inspection.confidence if inspection.confidence is not None else 'not recorded'}

Use only the trusted SOP passages below. Do not use general knowledge. Do not claim a
defect subtype, physical cause, severity, root cause, product disposition, release,
repair, scrap, or equipment action unless the passages explicitly support it. The
original Defective prediction is not proof of those facts.

Return JSON only in this exact shape:
{{"summary":"short factual summary","actions":[{{"action":"one supported next step","source_ids":["S1"]}}]}}

Every action must be directly supported by one or more source IDs. Keep the action list
short and use the applicable mapped SOPs together where relevant. If the passages do
not support a safe action, return an empty actions list.

TRUSTED SOP PASSAGES:
{source_prompt}
"""
    model = os.getenv("OPENROUTER_LLM_MODEL", "liquid/lfm-2.5-2.6b:free")
    fallbacks = [item.strip() for item in os.getenv("OPENROUTER_LLM_FALLBACK_MODELS", "openrouter/free").split(",") if item.strip() and item.strip() != model]
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a strict manufacturing quality assistant. Return only valid JSON grounded in the supplied passages."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    if fallbacks:
        payload["models"] = fallbacks
    last_error = None
    for attempt in range(3):
        try:
            response = OpenRouterClient().post("/chat/completions", payload)
            content = response["choices"][0]["message"]["content"]
            result = _parse_llm_json(content)
            break
        except Exception as exc:
            last_error = exc
            if attempt == 2:
                raise EvidenceError(f"Incident generation failed: {exc}") from exc
            time.sleep(0.5 * (2 ** attempt))
    else:  # pragma: no cover - loop either breaks or raises
        raise EvidenceError(f"Incident generation failed: {last_error}")

    summary = str(result.get("summary", "")).strip()
    raw_actions = result.get("actions")
    if not summary or not isinstance(raw_actions, list):
        raise EvidenceError("Incident generation omitted the required summary or actions.")
    source_map = {source["source_id"]: source for source in sources}
    actions = []
    for raw_action in raw_actions[:8]:
        if not isinstance(raw_action, dict):
            raise EvidenceError("Incident generation returned an invalid action.")
        action_text = str(raw_action.get("action", "")).strip()
        source_ids = raw_action.get("source_ids")
        if not action_text or not isinstance(source_ids, list) or not source_ids:
            raise EvidenceError("Every generated action requires supporting source IDs.")
        if any(str(source_id) not in source_map for source_id in source_ids):
            raise EvidenceError("Incident generation referenced an unavailable SOP source.")
        for source_id in source_ids:
            source = source_map[str(source_id)]
            actions.append({
                "action": action_text,
                "source_document_id": source["document_id"],
                "source_document_name": source["document_name"],
                "revision": source["revision"],
                "page_number": source["page_number"],
                "supporting_passage": source["passage"],
                "source_link": _source_link(source["document_id"], source["page_number"]),
            })
    if not actions:
        raise EvidenceError("Incident generation returned no supported actions.")
    references = [{
        "source_document_id": source["document_id"],
        "source_document_name": source["document_name"],
        "revision": source["revision"],
        "page_number": source["page_number"],
        "supporting_passage": source["passage"],
        "source_link": _source_link(source["document_id"], source["page_number"]),
    } for source in sources]
    return {"summary": summary, "actions": actions, "references": references}


def _rag_pages(inspection, rows: list[dict[str, str]]) -> list[dict[str, Any]] | None:
    """Retrieve only indexed, mapped SOPs through the shared RAG retriever.

    ``None`` means the Round 3 indexing command has not been run yet; callers
    may use the synchronous PDF fallback. An empty list means indexing exists
    but retrieval found no evidence and must be treated as insufficient.
    """
    document_ids = [row["document_id"] for row in rows]
    indexed = {}
    for row in rows:
        chunks = RAGDocumentChunk.objects.filter(
            manual__document_id=row["document_id"],
            manual__revision=row["revision"],
            manual__ingestion_status="completed",
        ).exists()
        if not chunks:
            return None
        indexed[row["document_id"]] = row

    retriever = Retriever(top_k=10)
    pages = []
    for document_id in document_ids:
        row = indexed[document_id]
        question = (
            f"Quality incident review for product {inspection.product.product_code}: "
            f"find the applicable containment, evidence, review, and escalation actions in {document_id}."
        )
        chunks = retriever.retrieve(
            question,
            inspection.product.product_code,
            allowed_documents={(row["pdf_filename"], row["revision"])},
        )
        if not chunks:
            raise EvidenceError(
                f"RAG retrieval returned no relevant evidence for required SOP {document_id}."
            )
        for chunk in chunks:
            pages.append({
                "document_id": document_id,
                "document_name": row["pdf_filename"],
                "revision": row["revision"],
                "page_number": chunk.page_number,
                "passage": chunk.passage,
            })
    return pages


def build_evidence(inspection) -> dict[str, Any]:
    """Retrieve every required mapped SOP and create traceable actions.

    Indexed SOPs use the shared RAG retriever. A synchronous page-extraction
    fallback keeps the challenge usable before the indexing command is run,
    while still enforcing exact mapping and source isolation.
    """
    rows = mapped_sops(inspection.product.product_code)
    for row in rows:
        if not (PACK_ROOT / "SOPs" / row["pdf_filename"]).is_file():
            raise EvidenceError(
                f"Required SOP {row['document_id']} revision {row['revision']} is unavailable."
            )
    pages = _rag_pages(inspection, rows)
    if pages is None:
        pages = []
        for row in rows:
            pdf_path = PACK_ROOT / "SOPs" / row["pdf_filename"]
            if not pdf_path.is_file():
                raise EvidenceError(f"Required SOP {row['document_id']} revision {row['revision']} is unavailable.")
            try:
                extracted = extract_pages(
                    pdf_path,
                    machine_id=inspection.product.product_code,
                    manual_id=row["document_id"],
                    document_name=row["pdf_filename"],
                    revision=row["revision"],
                )
            except Exception as exc:
                raise EvidenceError(f"Required SOP {row['document_id']} could not be read: {exc}") from exc
            if not extracted:
                raise EvidenceError(f"Required SOP {row['document_id']} contains no readable evidence.")
            pages.extend({
                "document_id": row["document_id"],
                "document_name": row["pdf_filename"],
                "revision": row["revision"],
                "page_number": page.page_number,
                "passage": page.text,
            } for page in extracted)

    return generate_incident_content(inspection, pages)


def create_incident_for_inspection(inspection_id, user, *, simulate_missing_evidence=False):
    """Create one incident safely; shared by the synchronous and Celery paths."""
    from django.db import IntegrityError, transaction
    from inspections.models import IncidentReview, Inspection, QualityIncident

    try:
        with transaction.atomic():
            inspection = Inspection.objects.select_for_update().select_related("product").get(
                inspection_id=inspection_id, submitted_by=user
            )
            existing = QualityIncident.objects.filter(inspection=inspection).first()
            if existing:
                return existing, False
            if inspection.status != Inspection.Status.COMPLETED or inspection.predicted_class != "Defective":
                raise IncidentEligibilityError(
                    "Only a completed inspection with the original Defective prediction can create a quality incident."
                )
            incident = QualityIncident.objects.create(
                inspection=inspection,
                product_id=inspection.product.product_code,
                original_prediction=inspection.predicted_class,
                model_version=inspection.model_version,
                created_by=user,
            )
            IncidentReview.objects.create(incident=incident, status=IncidentReview.Status.PENDING)
            try:
                if settings.DEBUG and simulate_missing_evidence:
                    raise EvidenceError("Demo mode: a required mapped SOP was marked unavailable for this test.")
                evidence = build_evidence(inspection)
                incident.summary = evidence["summary"]
                incident.suggested_actions = evidence["actions"]
                incident.source_references = evidence["references"]
                incident.evidence_status = QualityIncident.EvidenceStatus.SUFFICIENT
            except Exception as exc:
                incident.evidence_status = QualityIncident.EvidenceStatus.INSUFFICIENT
                incident.evidence_reason = str(exc) or "SOP evidence or incident generation failed."
                incident.summary = f"Inspection {inspection.inspection_id} was flagged by the original model as Defective. Manual review is required because the required SOP evidence is unavailable."
            incident.save()
            return incident, True
    except IntegrityError:
        existing = QualityIncident.objects.filter(inspection__inspection_id=inspection_id).first()
        if existing:
            return existing, False
        raise


def source_pdf(document_id: str):
    """Resolve a source only through the mapping, never by a guessed filename."""
    rows = []
    with MAPPING_PATH.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("document_id") == document_id]
    if not rows:
        raise EvidenceError("Source document is not present in the supplied mapping.")
    path = PACK_ROOT / "SOPs" / rows[0]["pdf_filename"]
    if not path.is_file():
        raise EvidenceError("Source PDF is unavailable.")
    return path, rows[0]
