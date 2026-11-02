from __future__ import annotations

from celery import shared_task

from .ingestion import ingest_manual
from .models import Manual


def _is_daily_provider_limit(error: Exception) -> bool:
    message = str(error).lower()
    return "free-models-per-day" in message or "daily limit" in message


def queue_manual_ingestion(manual_id: int) -> None:
    """Publish ingestion after the surrounding database transaction commits."""

    ingest_manual_task.delay(manual_id)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def ingest_manual_task(self, manual_id: int) -> dict:
    """Extract, embed, and index one uploaded manual in the background."""

    try:
        manual = Manual.objects.get(pk=manual_id)
    except Manual.DoesNotExist:
        return {"status": "missing", "manual_id": manual_id}

    if not manual.file:
        Manual.objects.filter(pk=manual.pk).update(
            ingestion_status=Manual.IngestionStatus.FAILED
        )
        return {"status": "failed", "manual_id": manual.pk, "error": "PDF file is missing."}

    Manual.objects.filter(pk=manual.pk).update(
        ingestion_status=Manual.IngestionStatus.PROCESSING
    )

    try:
        result = ingest_manual(
            manual.file.path,
            machine_id=manual.machine.machine_id,
            manual_id=manual.pk,
            document_name=manual.document_name,
            revision=manual.revision,
        )
    except Exception as exc:
        if _is_daily_provider_limit(exc):
            # Retrying cannot help until OpenRouter's daily quota resets. Mark
            # the manual failed immediately so Admin does not show a task
            # stuck in pending/processing while Celery retries indefinitely.
            Manual.objects.filter(pk=manual.pk).update(
                ingestion_status=Manual.IngestionStatus.FAILED
            )
            return {
                "status": "failed",
                "manual_id": manual.pk,
                "error": (
                    "OpenRouter free-model daily limit reached. "
                    "Wait for the quota reset or configure a funded/new API key."
                ),
            }
        if self.request.retries < self.max_retries:
            Manual.objects.filter(pk=manual.pk).update(
                ingestion_status=Manual.IngestionStatus.PENDING
            )
            raise self.retry(exc=exc)
        Manual.objects.filter(pk=manual.pk).update(
            ingestion_status=Manual.IngestionStatus.FAILED
        )
        return {"status": "failed", "manual_id": manual.pk, "error": str(exc)}

    Manual.objects.filter(pk=manual.pk).update(
        ingestion_status=Manual.IngestionStatus.COMPLETE
    )
    return {"status": "completed", "manual_id": manual.pk, **result}
