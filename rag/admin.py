from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display
from unfold.contrib.filters.admin import RangeDateTimeFilter, ChoicesDropdownFilter, RelatedDropdownFilter

from .models import RAGQueryLog, RAGDocumentChunk


@admin.register(RAGQueryLog)
class RAGQueryLogAdmin(ModelAdmin):
    list_display = (
        "machine",
        "display_status",
        "short_question",
        "user",
        "display_citations_count",
        "created_at",
    )
    list_filter = (
        ("status", ChoicesDropdownFilter),
        ("machine", RelatedDropdownFilter),
        ("created_at", RangeDateTimeFilter),
    )
    search_fields = (
        "question",
        "answer",
        "machine__machine_id",
        "machine__machine_name",
        "user__username",
    )
    readonly_fields = (
        "user",
        "machine",
        "question",
        "answer",
        "status",
        "citations",
        "created_at",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 25

    fieldsets = (
        (
            "Query Details",
            {
                "fields": (
                    "machine",
                    "user",
                    "status",
                    "created_at",
                ),
                "description": "User identification and target equipment context for RAG query.",
            },
        ),
        (
            "Natural Language Exchange",
            {
                "fields": (
                    "question",
                    "answer",
                ),
            },
        ),
        (
            "Grounded Evidence & Citations",
            {
                "fields": ("citations",),
                "description": "Verifiable document passages, page numbers, and manual references.",
            },
        ),
    )

    @display(
        description="Query Status",
        label={
            "ANSWERED": "success",
            "INSUFFICIENT": "warning",
            "ERROR": "danger",
        },
    )
    def display_status(self, obj):
        return obj.status

    @display(description="Question Summary")
    def short_question(self, obj):
        if len(obj.question) > 65:
            return f"{obj.question[:65]}..."
        return obj.question

    @display(description="Citations", label=True)
    def display_citations_count(self, obj):
        count = len(obj.citations) if isinstance(obj.citations, list) else 0
        return f"{count} Source{'s' if count != 1 else ''}"


@admin.register(RAGDocumentChunk)
class RAGDocumentChunkAdmin(ModelAdmin):
    list_display = (
        "manual",
        "machine",
        "page_number",
        "chunk_index",
        "passage_id",
        "short_text",
        "created_at",
    )
    list_filter = (
        ("manual", RelatedDropdownFilter),
        ("machine", RelatedDropdownFilter),
        "page_number",
    )
    search_fields = (
        "chunk_text",
        "passage_id",
        "manual__document_id",
        "manual__document_name",
        "machine__machine_id",
    )
    autocomplete_fields = ("manual", "machine")
    readonly_fields = ("created_at",)
    ordering = ("manual", "page_number", "chunk_index")
    list_per_page = 30

    fieldsets = (
        (
            "Source Manual Reference",
            {
                "fields": (
                    "manual",
                    "machine",
                    "page_number",
                    "chunk_index",
                    "passage_id",
                ),
            },
        ),
        (
            "Extracted Text Passage",
            {
                "fields": ("chunk_text",),
            },
        ),
        (
            "Indexing Audit",
            {
                "fields": ("created_at",),
                "classes": ["collapse"],
            },
        ),
    )

    @display(description="Chunk Excerpt")
    def short_text(self, obj):
        if len(obj.chunk_text) > 80:
            return f"{obj.chunk_text[:80]}..."
        return obj.chunk_text
