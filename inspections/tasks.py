from celery import shared_task
from django.utils import timezone

from .models import Inspection
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
