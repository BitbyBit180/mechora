from celery import shared_task
from django.utils import timezone

from .models import Inspection, QualityIncidentBatch
from .services.quality_incidents import IncidentEligibilityError, create_incident_for_inspection
from .services.inference import predict


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def process_inspection(self, inspection_id):
    try:
        inspection = Inspection.objects.select_related("product").get(pk=inspection_id)
    except Inspection.DoesNotExist:
        return {"status": "missing", "inspection_id": inspection_id}
    if inspection.status != Inspection.Status.QUEUED:
        return {"status": inspection.status, "inspection_id": inspection_id}
    Inspection.objects.filter(pk=inspection.pk).update(status=Inspection.Status.PROCESSING)
    try:
        result = predict(inspection.image.path)
        inspection.predicted_class = result["predicted_class"]
        inspection.confidence = result["confidence"]
        inspection.defect_probability = result["defect_probability"]
        inspection.model_version = result["model_version"]
        inspection.status = Inspection.Status.COMPLETED
        inspection.completed_at = timezone.now()
        inspection.save(update_fields=[
            "predicted_class", "confidence", "defect_probability",
            "model_version", "status", "completed_at",
        ])
        return {"status": "completed", "inspection_id": inspection_id}
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        inspection.mark_failed(f"Inference failed: {exc}")
        return {"status": "failed", "inspection_id": inspection_id, "error": str(exc)}


@shared_task(bind=True)
def process_quality_incident_batch(self, batch_pk):
    try:
        batch = QualityIncidentBatch.objects.get(pk=batch_pk)
    except QualityIncidentBatch.DoesNotExist:
        return {"status": "missing", "batch_id": batch_pk}
    batch.status = QualityIncidentBatch.Status.PROCESSING
    batch.save(update_fields=["status", "updated_at"])
    for index, item in enumerate(batch.items):
        if item.get("status") == "completed":
            continue
        try:
            incident, created = create_incident_for_inspection(
                item["inspection_id"], batch.created_by,
                simulate_missing_evidence=bool(item.get("simulate_missing_evidence")),
            )
            item.update({"status": "completed", "incident_id": incident.pk, "created": created})
            batch.completed_items += 1
        except IncidentEligibilityError as exc:
            item.update({"status": "failed", "error": str(exc)})
            batch.failed_items += 1
        except Exception as exc:
            item.update({"status": "failed", "error": str(exc) or "Incident generation failed."})
            batch.failed_items += 1
        batch.items = list(batch.items)
        batch.save(update_fields=["items", "completed_items", "failed_items", "updated_at"])
    batch.status = QualityIncidentBatch.Status.FAILED if batch.failed_items and not batch.completed_items else QualityIncidentBatch.Status.COMPLETED
    batch.save(update_fields=["status", "updated_at"])
    return {"status": batch.status, "batch_id": str(batch.batch_id)}
