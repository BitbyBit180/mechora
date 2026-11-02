from django.contrib import admin
from django.db import transaction
import logging
from unfold.admin import ModelAdmin
from unfold.decorators import display
from unfold.contrib.filters.admin import RangeDateTimeFilter, ChoicesDropdownFilter, RelatedDropdownFilter

from .models import Manual
from .tasks import queue_manual_ingestion


logger = logging.getLogger(__name__)


@admin.register(Manual)
class ManualAdmin(ModelAdmin):
    list_display = (
        "document_id",
        "document_name",
        "machine",
        "revision",
        "display_status",
        "pdf_filename",
        "uploaded_at",
    )
    list_filter = (
        ("ingestion_status", ChoicesDropdownFilter),
        ("machine", RelatedDropdownFilter),
        "revision",
        ("uploaded_at", RangeDateTimeFilter),
    )
    search_fields = (
        "document_id",
        "document_name",
        "machine__machine_id",
        "machine__model",
        "machine__machine_name",
        "pdf_filename",
    )
    autocomplete_fields = ("machine", "uploaded_by")
    readonly_fields = ("uploaded_at", "updated_at")
    list_per_page = 20
    ordering = ("-uploaded_at",)

    def save_model(self, request, obj, form, change):
        file_uploaded = bool(form.cleaned_data.get("file"))
        if not change and not obj.uploaded_by_id:
            obj.uploaded_by = request.user
        if file_uploaded:
            obj.ingestion_status = Manual.IngestionStatus.PENDING
            if obj.file:
                obj.pdf_filename = obj.file.name.rsplit("/", 1)[-1]
        super().save_model(request, obj, form, change)
        if file_uploaded:
            manual_id = obj.pk

            def enqueue_ingestion():
                try:
                    queue_manual_ingestion(manual_id)
                except Exception:
                    logger.exception("Unable to queue ingestion for manual %s", manual_id)
                    Manual.objects.filter(pk=manual_id).update(
                        ingestion_status=Manual.IngestionStatus.FAILED
                    )

            transaction.on_commit(enqueue_ingestion)

    fieldsets = (
        (
            "Document Identification",
            {
                "fields": (
                    "document_id",
                    "machine",
                    "document_name",
                    "revision",
                ),
                "description": "Metadata associating technical documents with registered industrial machinery.",
            },
        ),
        (
            "File Asset & RAG Ingestion",
            {
                "fields": (
                    "pdf_filename",
                    "file",
                    "ingestion_status",
                ),
                "description": "PDF document upload and vector database ingestion lifecycle.",
            },
        ),
        (
            "Audit & Provenance",
            {
                "fields": (
                    "uploaded_by",
                    "uploaded_at",
                    "updated_at",
                ),
                "classes": ["collapse"],
            },
        ),
    )

    @display(
        description="Ingestion Status",
        label={
            "completed": "success",
            "processing": "warning",
            "pending": "info",
            "failed": "danger",
        },
    )
    def display_status(self, obj):
        return obj.ingestion_status
