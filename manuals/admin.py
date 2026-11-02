from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display
from unfold.contrib.filters.admin import RangeDateTimeFilter, ChoicesDropdownFilter, RelatedDropdownFilter

from .models import Manual


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
