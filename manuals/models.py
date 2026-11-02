from django.conf import settings
from django.db import models


class Manual(models.Model):
    INGESTION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    document_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name="Document ID",
        help_text="Standard document identifier (e.g., HP-OPS-01, AC-OM-01)",
    )
    machine = models.ForeignKey(
        "machines.Machine",
        on_delete=models.CASCADE,
        related_name="manuals",
        verbose_name="Associated Machine",
    )
    document_name = models.CharField(
        max_length=255,
        verbose_name="Document Title",
        help_text="Descriptive manual title (e.g., Operations, limits, alarms)",
    )
    revision = models.CharField(
        max_length=20,
        default="1.0",
        verbose_name="Revision",
        help_text="Document revision number or code (e.g., 1.0, Rev B)",
    )
    pdf_filename = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="PDF Filename",
        help_text="Original PDF document filename (e.g., HP200_Operations_Rev1_0.pdf)",
    )
    file = models.FileField(
        upload_to="manuals/",
        null=True,
        blank=True,
        verbose_name="Manual PDF File",
        help_text="Uploaded PDF document stored in protected manual storage",
    )
    ingestion_status = models.CharField(
        max_length=20,
        choices=INGESTION_STATUS_CHOICES,
        default="pending",
        verbose_name="Ingestion Status",
        help_text="RAG vector ingestion lifecycle status",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_manuals",
        verbose_name="Uploaded By",
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Uploaded At",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Last Updated",
    )

    class Meta:
        verbose_name = "Manual"
        verbose_name_plural = "Manuals"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.document_id} - {self.document_name} (Rev {self.revision})"
