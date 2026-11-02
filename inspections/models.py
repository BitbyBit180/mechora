from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class InspectionBatch(models.Model):
    batch_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="inspection_batches")
    total_items = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.batch_id)

    @property
    def completed_count(self):
        return self.items.filter(status=Inspection.Status.COMPLETED).count()

    @property
    def failed_count(self):
        return self.items.filter(status=Inspection.Status.FAILED).count()


class Inspection(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class ReviewStatus(models.TextChoices):
        NOT_ELIGIBLE = "not_eligible", "Not eligible"
        PENDING = "pending", "Pending review"
        CONFIRMED = "confirmed", "Confirmed"
        CORRECTED = "corrected", "Corrected"

    inspection_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    batch = models.ForeignKey(InspectionBatch, null=True, blank=True, on_delete=models.SET_NULL, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="inspections")
    image = models.ImageField(upload_to="inspections/%Y/%m/%d/")
    original_filename = models.CharField(max_length=255)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="inspections")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_inspections")
    predicted_class = models.CharField(max_length=32, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    defect_probability = models.FloatField(null=True, blank=True)
    model_version = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def review_status(self):
        if self.status != self.Status.COMPLETED:
            return self.ReviewStatus.NOT_ELIGIBLE
        if hasattr(self, "review"):
            return self.review.review_status
        return self.ReviewStatus.PENDING

    def mark_failed(self, reason):
        self.status = self.Status.FAILED
        self.failure_reason = reason
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "failure_reason", "completed_at"])

    def __str__(self):
        return str(self.inspection_id)


class InspectionReview(models.Model):
    inspection = models.OneToOneField(Inspection, on_delete=models.CASCADE, related_name="review")
    reviewed_class = models.CharField(max_length=32)
    review_status = models.CharField(max_length=20, choices=Inspection.ReviewStatus.choices)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="inspection_reviews")
    comment = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reviewed_at"]

    def __str__(self):
        return f"Review for {self.inspection.inspection_id}"
